import json
import os
import sys
from pathlib import Path

from tag_data_engineering.extractors.entra_users_extractor import EntraUsersExtractor
from tag_data_engineering.models import ExtractionMetadata


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    while True:
        if (current / "pyproject.toml").exists():
            return current
        if current.parent == current:
            return start.resolve()
        current = current.parent


REPO_ROOT = _find_repo_root(Path(__file__).parent)
sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key:
            env[key.strip()] = value.strip()
    return env


def _apply_env(env: dict[str, str]) -> None:
    for key, value in env.items():
        if key not in os.environ:
            os.environ[key] = value


def _load_metadata() -> ExtractionMetadata:
    metadata_path = REPO_ROOT / "src" / "tag_data_engineering" / "transformations" / "landing" / "entra_users" / "metadata.json"
    return ExtractionMetadata.from_json_file(metadata_path)


def _apply_env_config(metadata: ExtractionMetadata) -> None:
    cfg = dict(metadata.extractor_config or {})
    tenant_id = os.getenv("ENTRA_TENANT_ID")
    client_id = os.getenv("ENTRA_CLIENT_ID")
    client_secret = os.getenv("ENTRA_CLIENT_SECRET")

    if not tenant_id or not client_id or not client_secret:
        missing = [
            k
            for k, v in {
                "ENTRA_TENANT_ID": tenant_id,
                "ENTRA_CLIENT_ID": client_id,
                "ENTRA_CLIENT_SECRET": client_secret,
            }.items()
            if not v
        ]
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    cfg["tenant_id"] = tenant_id
    cfg["client_id"] = client_id
    cfg["client_secret"] = client_secret

    base_url = os.getenv("ENTRA_BASE_URL")
    if base_url:
        cfg["base_url"] = base_url

    endpoint = os.getenv("ENTRA_ENDPOINT")
    if endpoint:
        cfg["endpoint"] = endpoint

    metadata.extractor_config = cfg


def main() -> None:
    env_path = REPO_ROOT / ".env.verint"
    env = _load_env_file(env_path)
    _apply_env(env)

    metadata = _load_metadata()
    _apply_env_config(metadata)

    extractor = EntraUsersExtractor()
    batch = next(extractor.extract(metadata))
    records = batch.records

    output_dir = REPO_ROOT / "entra_users_live_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "entra_users_live.json"
    output_path.write_text(json.dumps(records, indent=2))

    sample_limit = int(os.getenv("ENTRA_SAMPLE_LIMIT", "3"))
    print(f"Total records: {len(records)}")
    print(f"Wrote output: {output_path}")
    if records:
        sample = records[:sample_limit]
        print("First record keys:")
        print(list(sample[0].keys()))
        print("Sample records:")
        # print(json.dumps(sample, indent=2)[:2000])


if __name__ == "__main__":
    main()
