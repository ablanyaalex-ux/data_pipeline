# ruff: noqa: F821
from pyspark.sql import functions as F


OLD_RESULTS_PATH = "ops_appeals_old_20260106.csv"
NEW_RESULTS_PATH = "appeals_export/part-00000-1eab8bcd-c95c-4361-bbec-476aa18e4c6c-c000.csv"

# Load data using Spark
print("Loading old results using Spark...")
df_old = spark.read.csv(f"Files/{OLD_RESULTS_PATH}", header=True, inferSchema=True)
print(f"Old results: {df_old.count():,} cases")

print("Loading new results using Spark...")
df_new = spark.read.csv(f"Files/{NEW_RESULTS_PATH}", header=True, inferSchema=True)
print(f"New results: {df_new.count():,} cases")

# Show sample columns
print("Old columns (sample):", df_old.columns[:15])
print("New columns (sample):", df_new.columns[:15])


print("\nPreparing comparison columns...")

# Computed columns matching the final SELECT aggregations
df_new = df_new.withColumn("new_has_appeal", F.col("has_decision_dre_manager") * F.col("has_appeal") * F.col("has_pending_appeal_status"))

df_new = df_new.withColumn("new_has_accepted", F.col("has_decision_dre_manager") * F.col("has_appeal") * F.col("has_pending_appeal_status") * F.col("has_accepted_appeal_action"))

df_new = df_new.withColumn(
    "new_has_rejected", F.col("has_decision_dre_manager") * F.col("has_appeal") * F.col("has_pending_appeal_status") * F.when((F.col("has_rejected_appeal_status") == 1) | (F.col("has_rejected_appeal_action") == 1), 1).otherwise(0)
)

df_new = df_new.withColumn("new_has_attempted", F.col("has_decision_dre_manager") * F.col("has_attempted_appeal"))

df_new = df_new.withColumn("new_has_consumer_appeal", F.col("has_decision_dre_manager") * F.col("has_appeal") * F.col("has_pending_appeal_status") * F.col("has_consumer_appeal"))

df_new = df_new.withColumn("new_has_company_appeal", F.col("has_decision_dre_manager") * F.col("has_appeal") * F.col("has_pending_appeal_status") * F.col("has_company_appeal"))

df_new = df_new.withColumn("new_has_decision", F.col("has_decision_dre_manager"))

print("✅ Computed columns added to new data")

print("\n" + "=" * 80)
print("AVAILABLE DREs")
print("=" * 80)

dres_old = df_old.groupBy("Coach").agg(F.count("Case_ID").alias("Total_Cases"), F.sum(F.col("Case Has an Appeal")).alias("Total_Appeals")).orderBy(F.desc("Total_Cases"))

print("\nTop 20 DREs by case count (from old data):")
dres_old.show(20, truncate=False)

# PICK A DRE HERE - Change this to test different DREs
SELECTED_DRE = dres_old.first()["Coach"]  # Pick the top DRE
print(f"\n📌 Selected DRE: {SELECTED_DRE}")


df_old_dre = df_old.filter(F.col("Coach") == SELECTED_DRE).cache()
df_new_dre = df_new.filter(F.col("dre_coach") == SELECTED_DRE).cache()

print(f"\n{SELECTED_DRE}")
print(f"  Old data: {df_old_dre.count():,} cases")
print(f"  New data: {df_new_dre.count():,} cases")

# Compare aggregated metrics for this DRE
print("\n" + "=" * 80)
print(f"AGGREGATE METRICS COMPARISON - {SELECTED_DRE}")
print("=" * 80)

# Calculate metrics
old_decisions = df_old_dre.count()
new_decisions = df_new_dre.agg(F.sum("new_has_decision")).collect()[0][0] or 0

old_appeals = df_old_dre.agg(F.sum(F.col("Case Has an Appeal"))).collect()[0][0] or 0
new_appeals = df_new_dre.agg(F.sum("new_has_appeal")).collect()[0][0] or 0

old_accepted = df_old_dre.agg(F.sum(F.col("Case Has an Accepted Appeal"))).collect()[0][0] or 0
new_accepted = df_new_dre.agg(F.sum("new_has_accepted")).collect()[0][0] or 0

old_rejected = df_old_dre.agg(F.sum(F.col("Case Has a Rejected Appeal"))).collect()[0][0] or 0
new_rejected = df_new_dre.agg(F.sum("new_has_rejected")).collect()[0][0] or 0

old_attempted = df_old_dre.agg(F.sum(F.col("Case Has an Attempted Appeal"))).collect()[0][0] or 0
new_attempted = df_new_dre.agg(F.sum("new_has_attempted")).collect()[0][0] or 0

old_consumer = df_old_dre.filter(F.col("Appealed_By_Consumer") == "Yes").count()
new_consumer = df_new_dre.agg(F.sum("new_has_consumer_appeal")).collect()[0][0] or 0

old_company = df_old_dre.filter(F.col("Appealed_By_PC") == "Yes").count()
new_company = df_new_dre.agg(F.sum("new_has_company_appeal")).collect()[0][0] or 0

# Print comparison table
metrics = [
    ("Cases with Decision", old_decisions, new_decisions),
    ("Appeals", old_appeals, new_appeals),
    ("Accepted Appeals", old_accepted, new_accepted),
    ("Rejected Appeals", old_rejected, new_rejected),
    ("Attempted Appeals", old_attempted, new_attempted),
    ("Consumer Appeals", old_consumer, new_consumer),
    ("Company Appeals", old_company, new_company),
]

print(f"{'Metric':<25} {'Old':>10} {'New':>10} {'Diff':>10} {'Match':>10}")
print("-" * 70)
for metric_name, old_val, new_val in metrics:
    diff = new_val - old_val
    match = "✅" if old_val == new_val else "❌"
    print(f"{metric_name:<25} {int(old_val):>10,} {int(new_val):>10,} {int(diff):>10,} {match:>10}")

# Average days in appeal
old_avg_days = df_old_dre.filter(F.col("Case Has an Appeal") == 1).agg(F.avg("Days in Appeal")).collect()[0][0]
new_avg_days = df_new_dre.filter(F.col("new_has_appeal") == 1).agg(F.avg("days_in_appeal")).collect()[0][0]

print("\nAvg Days in Appeal:")
print(f"  Old: {old_avg_days:.1f}" if old_avg_days else "  Old: N/A")
print(f"  New: {new_avg_days:.1f}" if new_avg_days else "  New: N/A")
if old_avg_days and new_avg_days:
    print(f"  Diff: {new_avg_days - old_avg_days:.1f}")

# Merge datasets for comparison
# Create a clean merge without duplicate columns
merged = (
    df_old_dre.alias("old")
    .join(df_new_dre.alias("new"), F.col("old.Case_ID") == F.col("new.case_id"), how="outer")
    .select(
        F.coalesce(F.col("old.Case_ID"), F.col("new.case_id")).alias("case_id"),
        # Old query columns (prefixed where needed)
        F.col("old.`Case Has an Appeal`"),
        F.col("old.`Case Has an Accepted Appeal`"),
        F.col("old.`Case Has a Rejected Appeal`"),
        F.col("old.`Case Has an Attempted Appeal`"),
        F.col("old.Appeal_Status_Outcome"),
        F.col("old.Appealed_By_Consumer"),
        F.col("old.Appealed_By_PC"),
        F.col("old.`Days in Appeal`"),
        # New query columns
        F.col("new.new_has_appeal"),
        F.col("new.new_has_accepted"),
        F.col("new.new_has_rejected"),
        F.col("new.new_has_attempted"),
        F.col("new.new_has_consumer_appeal"),
        F.col("new.new_has_company_appeal"),
        F.col("new.has_appeal"),
        F.col("new.has_pending_appeal_status"),
        F.col("new.has_decision_dre_manager"),
        F.col("new.has_accepted_appeal_status"),
        F.col("new.has_accepted_appeal_action"),
        F.col("new.has_rejected_appeal_status"),
        F.col("new.has_rejected_appeal_action"),
        F.col("new.has_attempted_appeal"),
        F.col("new.has_consumer_appeal"),
        F.col("new.has_raw_consumer_appeal"),
        F.col("new.has_internal_appeal"),
        F.col("new.has_company_appeal"),
        F.col("new.days_in_appeal"),
    )
    .cache()
)

print(f"\nMerged dataset: {merged.count():,} cases")

# Find mismatched cases - Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - APPEALS")
print("=" * 80)

appeal_mismatches = merged.filter(F.col("Case Has an Appeal") != F.col("new_has_appeal")).select(
    "case_id", F.col("Case Has an Appeal").alias("old_has_appeal"), "new_has_appeal", "Appeal_Status_Outcome", "has_appeal", "has_pending_appeal_status", "has_decision_dre_manager"
)

mismatch_count = appeal_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    appeal_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")

# Find mismatched cases - Accepted Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - ACCEPTED APPEALS")
print("=" * 80)

accepted_mismatches = merged.filter(F.col("Case Has an Accepted Appeal") != F.col("new_has_accepted")).select(
    "case_id", F.col("Case Has an Accepted Appeal").alias("old_has_accepted"), "new_has_accepted", "Appeal_Status_Outcome", "has_accepted_appeal_status", "has_accepted_appeal_action"
)

mismatch_count = accepted_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    accepted_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")

# Find mismatched cases - Rejected Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - REJECTED APPEALS")
print("=" * 80)

rejected_mismatches = merged.filter(F.col("Case Has a Rejected Appeal") != F.col("new_has_rejected")).select(
    "case_id", F.col("Case Has a Rejected Appeal").alias("old_has_rejected"), "new_has_rejected", "Appeal_Status_Outcome", "has_rejected_appeal_status", "has_rejected_appeal_action"
)

mismatch_count = rejected_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    rejected_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")

# Find mismatched cases - Attempted Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - ATTEMPTED APPEALS")
print("=" * 80)

attempted_mismatches = merged.filter(F.col("Case Has an Attempted Appeal") != F.col("new_has_attempted")).select(
    "case_id", F.col("Case Has an Attempted Appeal").alias("old_has_attempted"), "new_has_attempted", "Appeal_Status_Outcome", "has_attempted_appeal"
)

mismatch_count = attempted_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    attempted_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")

# Find mismatched cases - Consumer Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - CONSUMER APPEALS")
print("=" * 80)

consumer_mismatches = (
    merged.withColumn("old_consumer_appeal", F.when(F.col("Appealed_By_Consumer") == "Yes", 1).otherwise(0))
    .filter(F.col("old_consumer_appeal") != F.col("new_has_consumer_appeal"))
    .select("case_id", "Appealed_By_Consumer", "new_has_consumer_appeal", "has_consumer_appeal", "has_raw_consumer_appeal", "has_internal_appeal")
)

mismatch_count = consumer_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    consumer_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")

# Find mismatched cases - Company Appeals
print("\n" + "=" * 80)
print("MISMATCHED CASES - COMPANY/SUPPLIER APPEALS")
print("=" * 80)

company_mismatches = (
    merged.withColumn("old_company_appeal", F.when(F.col("Appealed_By_PC") == "Yes", 1).otherwise(0))
    .filter(F.col("old_company_appeal") != F.col("new_has_company_appeal"))
    .select("case_id", "Appealed_By_PC", "new_has_company_appeal", "has_company_appeal")
)

mismatch_count = company_mismatches.count()
print(f"\nTotal mismatches: {mismatch_count:,}")
if mismatch_count > 0:
    print("\nFirst 20 mismatches:")
    company_mismatches.show(20, truncate=False)
else:
    print("✅ No mismatches!")


# Deep dive into a specific case
def investigate_case(case_id):
    """Deep dive into a specific case to see all flags"""
    print(f"\n{'=' * 80}")
    print(f"CASE INVESTIGATION: {case_id}")
    print(f"{'=' * 80}")

    old_case = df_old.filter(F.col("Case_ID") == case_id)
    new_case = df_new.filter(F.col("case_id") == case_id)

    if old_case.count() == 0:
        print("❌ Case not found in old data")
    else:
        print("\nOLD DATA:")
        old_case.select(
            "Coach",
            F.col("Case Has an Appeal").alias("Has_Appeal"),
            F.col("Case Has an Accepted Appeal").alias("Has_Accepted"),
            F.col("Case Has a Rejected Appeal").alias("Has_Rejected"),
            F.col("Case Has an Attempted Appeal").alias("Has_Attempted"),
            "Appeal_Status_Outcome",
            F.col("Days in Appeal").alias("Days_In_Appeal"),
        ).show(truncate=False)

    if new_case.count() == 0:
        print("\n❌ Case not found in new data")
    else:
        print("\nNEW DATA:")
        new_case.select(
            "dre_coach",
            "has_decision_dre_manager",
            "has_appeal",
            "has_pending_appeal_status",
            "has_accepted_appeal_status",
            "has_accepted_appeal_action",
            "has_rejected_appeal_status",
            "has_rejected_appeal_action",
            "has_attempted_appeal",
            "days_in_appeal",
            "new_has_appeal",
            "new_has_accepted",
            "new_has_rejected",
            "new_has_attempted",
        ).show(truncate=False)


# Example usage - uncomment and change case_id:
# investigate_case(12345)
