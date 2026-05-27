from tag_data_engineering.connectors.lakehouse_connector import LakehouseConnector


class LocalLakehouseConnector(LakehouseConnector):
    def get_files_path(self, entity: str, run_id: str | None = None) -> str:
        if run_id:
            return f"{self.base_path}/Files/{entity}/{run_id}/"
        return f"{self.base_path}/Files/{entity}/*/"

    def mkdirs(self, path: str) -> None:
        pass

    def write_file(self, path: str, content: str) -> None:
        # NOTE(krishan711): this is complex because spark doesnt have any way to just write a single file
        # it always creates a directory with part files, even if there is just one part. so we join it up.
        rdd = self.spark.sparkContext.parallelize([content], 1)
        # Use saveAsTextFile which creates a directory, then rename the part file
        temp_path = f"{path}_temp"
        rdd.saveAsTextFile(temp_path)
        # Get Hadoop filesystem with proper configuration (includes S3A settings)
        hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()  # type: ignore[not-callable]
        uri = self.spark.sparkContext._jvm.java.net.URI(path)  # type: ignore[not-callable]
        fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)  # type: ignore[not-callable]
        # Find the part file and move it to the target path
        temp_path_obj = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(temp_path)  # type: ignore[not-callable]
        target_path_obj = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path)  # type: ignore[not-callable]
        # Get the part file (there should only be one since we used numSlices=1)
        files = fs.listStatus(temp_path_obj)
        part_file = None
        for file in files:
            if file.getPath().getName().startswith("part-"):
                part_file = file.getPath()
                break
        if part_file:
            # Delete target if it exists (recursive in case it's a directory)
            if fs.exists(target_path_obj):
                fs.delete(target_path_obj, True)
            # Rename part file to target
            fs.rename(part_file, target_path_obj)
        # Clean up temp directory
        fs.delete(temp_path_obj, True)

    def read_file(self, path: str) -> str:
        rdd = self.spark.sparkContext.textFile(path)
        return "\n".join(rdd.collect())

    def delete_dir(self, path: str) -> None:
        hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()  # type: ignore[not-callable]
        uri = self.spark.sparkContext._jvm.java.net.URI(path)  # type: ignore[not-callable]
        fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)  # type: ignore[not-callable]
        fs_path = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path)  # type: ignore[not-callable]
        fs.delete(fs_path, True)  # True = recursive

    def path_exists(self, path: str) -> bool:
        hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()  # type: ignore[not-callable]
        uri = self.spark.sparkContext._jvm.java.net.URI(path)  # type: ignore[not-callable]
        fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)  # type: ignore[not-callable]
        fs_path = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path)  # type: ignore[not-callable]
        return fs.exists(fs_path)

    def list_dir(self, path: str) -> list[tuple[str, str]]:
        hadoop_conf = self.spark.sparkContext._jsc.hadoopConfiguration()  # type: ignore[not-callable]
        uri = self.spark.sparkContext._jvm.java.net.URI(path)  # type: ignore[not-callable]
        fs = self.spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)  # type: ignore[not-callable]
        fs_path = self.spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path)  # type: ignore[not-callable]

        if not fs.exists(fs_path):
            raise FileNotFoundError(f"Path not found: {path}")

        statuses = fs.listStatus(fs_path)
        return [(str(status.getPath().getName()), str(status.getPath().toString())) for status in statuses]

    def close(self) -> None:
        if self.spark:
            self.spark.stop()
