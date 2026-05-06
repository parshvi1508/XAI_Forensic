import json
import statistics
import time
import urllib.request

API_URL = "https://jainparshvi-xai-forensics-backend.hf.space"
REPEATS = 3

SAMPLES = [
    {
        "words": 5,
        "text": "The update works surprisingly well.",
    },
    {
        "words": 10,
        "text": "The product looks good, but the setup process felt exhausting.",
    },
    {
        "words": 20,
        "text": "I was not entirely unhappy with the result, although the confusing instructions made the whole experience slower than expected today.",
    },
    {
        "words": 50,
        "text": "After several attempts, the tool finally produced a useful answer, but the long waiting time, unclear labels, and inconsistent confidence scores made me unsure whether the model actually understood the sentence or simply reacted to a few strong words that looked positive in isolation during the test case today again.",
    },
]

ENDPOINTS = ["why", "flip", "disagree"]


def post(endpoint, text):
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_URL}/{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=240) as response:
        body = json.loads(response.read().decode("utf-8"))
    client_ms = round((time.perf_counter() - start) * 1000)

    return body.get("duration_ms", client_ms)


def fmt(ms):
    return f"{ms / 1000:.1f}s" if ms >= 1000 else f"{ms}ms"


print("Warming up backend...")
post("disagree", "The update works surprisingly well.")
print("Warmup done.\n")

results = []

for sample in SAMPLES:
    row = {"words": sample["words"]}
    print(f"Running {sample['words']}-word sample...")

    for endpoint in ENDPOINTS:
        timings = []
        for i in range(REPEATS):
            duration = post(endpoint, sample["text"])
            timings.append(duration)
            print(f"  /{endpoint} run {i + 1}: {fmt(duration)}")

        row[endpoint] = round(statistics.median(timings))

    results.append(row)
    print()

print("\nMarkdown table:\n")
print("| Words | WHY median | FLIP median | DISAGREE median |")
print("|---:|---:|---:|---:|")
for row in results:
    print(
        f"| {row['words']} | {fmt(row['why'])} | {fmt(row['flip'])} | {fmt(row['disagree'])} |"
    )