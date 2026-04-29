import json
import re
import html
import time
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


BOARDS_FILE = "boards.json"
KEYWORDS_FILE = "title_keywords.json"
MATCHED_JOBS_FILE = "matched_jobs.json"
CANDIDATE_TRUTH_SOURCE_FILE = "candidate_truth_source.json"
KEYWORD_PHRASE_MAP_FILE = "keyword_phrase_map.json"
CUSTOM_RESUME_OUTPUT_DIR = "custom_resume_json"
CANDIDATE_NAME = "Ben Warren"
TOP_N_FOR_GPT = 3
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


CONTENT_MAP = {
    "high": [
        "threat hunting",
        "incident response",
        "threat intelligence",
        "detection analysis",
        "siem",
        "soar",
        "edr",
        "customer-facing",
        "customer facing",
        "technical guidance",
        "security guidance",
        "python",
        "powershell",
        "rest api",
        "rest apis",
        "api usage",
        "technical account",
        "customer success",
        "executive business review",
        "executive business reviews"
    ],
    "medium": [
        "technical program management",
        "cross-functional",
        "cross functional",
        "stakeholder alignment",
        "roadmap",
        "security program",
        "identity and access management",
        "iam",
        "access controls",
        "api security",
        "automation"
    ],
    "negative": [
        "quota",
        "pipeline management",
        "closing large",
        "enterprise software sales",
        "workday",
        "hris",
        "netsuite",
        "android",
        "frontend",
        "front-end",
        "react",
        "typescript",
        "javascript",
        "fullstack",
        "full-stack",
        "backend software development"
    ]
}


CUSTOM_RESUME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "candidate_name",
        "target_role",
        "source_job",
        "resume_headline",
        "professional_summary",
        "core_skills",
        "tailored_experience",
        "req_phrase_alignment",
        "disallowed_or_unsupported_phrases",
        "quality_control"
    ],
    "properties": {
        "candidate_name": {"type": "string"},
        "target_role": {"type": "string"},
        "source_job": {
            "type": "object",
            "additionalProperties": False,
            "required": ["company", "job_id", "title", "location", "url", "content_score"],
            "properties": {
                "company": {"type": "string"},
                "job_id": {"type": ["string", "number"]},
                "title": {"type": "string"},
                "location": {"type": "string"},
                "url": {"type": "string"},
                "content_score": {"type": "number"}
            }
        },
        "resume_headline": {"type": "string"},
        "professional_summary": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"}
        },
        "core_skills": {
            "type": "array",
            "minItems": 8,
            "maxItems": 18,
            "items": {"type": "string"}
        },
        "tailored_experience": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["role_id", "company", "title", "date_range", "bullets"],
                "properties": {
                    "role_id": {"type": "string"},
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "date_range": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "generated_bullet",
                                "req_phrases_used",
                                "evidence_ids_used",
                                "confidence"
                            ],
                            "properties": {
                                "generated_bullet": {"type": "string"},
                                "req_phrases_used": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "evidence_ids_used": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"}
                                },
                                "confidence": {"type": "string", "enum": ["high", "medium"]}
                            }
                        }
                    }
                }
            }
        },
        "req_phrase_alignment": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["req_phrase", "evidence_ids", "confidence", "notes"],
                "properties": {
                    "req_phrase": {"type": "string"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "no_match"]},
                    "notes": {"type": "string"}
                }
            }
        },
        "disallowed_or_unsupported_phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["phrase", "reason"],
                "properties": {
                    "phrase": {"type": "string"},
                    "reason": {"type": "string"}
                }
            }
        },
        "quality_control": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "used_only_candidate_truth_source",
                "all_bullets_have_evidence_ids",
                "unsupported_claims_removed",
                "notes"
            ],
            "properties": {
                "used_only_candidate_truth_source": {"type": "boolean"},
                "all_bullets_have_evidence_ids": {"type": "boolean"},
                "unsupported_claims_removed": {"type": "boolean"},
                "notes": {"type": "string"}
            }
        }
    }
}


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in {path}: line {e.lineno}, column {e.colno}. "
            f"Fix this file before running GPT generation."
        ) from e


def fetch_greenhouse_jobs(board_token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    req = Request(url, headers={"User-Agent": "Project-Coin-Flip/0.1"})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_html(raw_html):
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def match_title(title, keywords):
    title_lower = title.lower()
    include_hits = [
        word for word in keywords.get("include", [])
        if re.search(rf"\b{re.escape(word.lower())}\b", title_lower)
    ]
    exclude_hits = [
        word for word in keywords.get("exclude", [])
        if re.search(rf"\b{re.escape(word.lower())}\b", title_lower)
    ]
    return include_hits, exclude_hits


def location_allowed(location, content_text=""):
    if not location:
        return False

    loc = location.lower()
    loc = loc.replace(",", " ").replace("-", " ").replace("/", " ")
    loc = " ".join(loc.split())

    is_remote = "remote" in loc
    is_us = bool(re.search(r"\b(us|usa|u\.s\.|united states)\b", loc))
    is_nc = bool(re.search(
        r"\b(nc|north carolina|raleigh|durham|cary|holly springs|fuquay|garner|chapel hill|charlotte|rtp|research triangle)\b",
        loc
    ))
    is_hybrid = "hybrid" in loc
    is_onsite = any(term in loc for term in ["onsite", "on site", "on-site", "in office", "in-office"])

    if is_remote and (is_us or is_nc):
        return True
    if (is_hybrid or is_onsite) and is_nc:
        return True
    if is_nc:
        return True
    return False


def content_match(job, content_map):
    text = f"{job.get('title', '')} {job.get('content_text', '')}".lower()
    high_hits = [term for term in content_map["high"] if term in text]
    medium_hits = [term for term in content_map["medium"] if term in text]
    negative_hits = [term for term in content_map["negative"] if term in text]

    score = (len(high_hits) * 3) + (len(medium_hits) * 1) - (len(negative_hits) * 3)

    if score >= 6:
        decision = "strong_match"
    elif score >= 3:
        decision = "review"
    else:
        decision = "reject"

    return {
        "content_score": score,
        "content_decision": decision,
        "content_high_hits": high_hits,
        "content_medium_hits": medium_hits,
        "content_negative_hits": negative_hits
    }


def normalize_job(board_token, job):
    return {
        "company": board_token,
        "board_token": board_token,
        "job_id": job.get("id"),
        "internal_job_id": job.get("internal_job_id"),
        "title": job.get("title", "").strip(),
        "location": job.get("location", {}).get("name", ""),
        "url": job.get("absolute_url", ""),
        "updated_at": job.get("updated_at", ""),
        "first_published": job.get("first_published", ""),
        "content_text": clean_html(job.get("content", "")),
    }


def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value)
    value = re.sub(r"\s+", "_", value.strip())
    return value[:150]


def select_top_jobs(matches, top_n=TOP_N_FOR_GPT):
    return sorted(
        matches,
        key=lambda job: (
            job.get("content_score", 0),
            1 if job.get("content_decision") == "strong_match" else 0,
            job.get("updated_at", "")
        ),
        reverse=True
    )[:top_n]


def build_resume_prompt(job, candidate_truth_source, keyword_phrase_map):
    return {
        "task": "Create the JSON input needed to generate a custom resume for this specific job requisition.",
        "hard_rules": [
            "Use ONLY the provided candidate_truth_source as verified candidate evidence.",
            "Do NOT invent tools, employers, metrics, titles, degrees, certifications, industries, platforms, responsibilities, or outcomes.",
            "Do NOT infer experience from adjacent skills.",
            "Do NOT use a req phrase unless it cleanly maps to at least one evidence_id.",
            "Every generated bullet must include generated_bullet, req_phrases_used, evidence_ids_used, and confidence.",
            "Only generate bullets with high or medium confidence.",
            "If a phrase is unsupported, place it in disallowed_or_unsupported_phrases instead of using it.",
            "Respect candidate_truth_source.constraints.do_not_claim."
        ],
        "candidate_name": CANDIDATE_NAME,
        "job_req": job,
        "candidate_truth_source": candidate_truth_source,
        "keyword_phrase_map": keyword_phrase_map
    }


def validate_resume_json(result):
    problems = []

    if not result.get("quality_control", {}).get("used_only_candidate_truth_source"):
        problems.append("quality_control.used_only_candidate_truth_source is not true")

    if not result.get("quality_control", {}).get("all_bullets_have_evidence_ids"):
        problems.append("quality_control.all_bullets_have_evidence_ids is not true")

    for role in result.get("tailored_experience", []):
        for bullet in role.get("bullets", []):
            if not bullet.get("evidence_ids_used"):
                problems.append(f"Bullet missing evidence IDs: {bullet.get('generated_bullet', '')}")
            if bullet.get("confidence") not in ["high", "medium"]:
                problems.append(f"Invalid bullet confidence: {bullet.get('confidence')}")

    if problems:
        raise ValueError("Generated resume JSON failed validation: " + "; ".join(problems))


def generate_custom_resume_json(client, job, candidate_truth_source, keyword_phrase_map):
    prompt_payload = build_resume_prompt(job, candidate_truth_source, keyword_phrase_map)

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are Project Coin Flip's resume tailoring engine. "
                    "Return only schema-valid JSON. You are truth-bound and evidence-bound. "
                    "Never add unsupported candidate claims."
                )
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False)
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "custom_resume_json",
                "schema": CUSTOM_RESUME_SCHEMA,
                "strict": True
            }
        }
    )

    result = json.loads(response.output_text)
    validate_resume_json(result)
    return result


def save_custom_resume_json(job, resume_json):
    output_dir = Path(CUSTOM_RESUME_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate = safe_filename(CANDIDATE_NAME)
    title = safe_filename(job.get("title", "Unknown Role"))
    filename = f"{candidate}_{title}.json"
    output_path = output_dir / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resume_json, f, indent=2, ensure_ascii=False)

    return output_path

def load_api_key_from_file(path="pcf_gpt_key.txt"):
    with open(path, "r") as f:
        return f.read().strip()

# Load API key from environment variable instead of local file
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY as an environment variable.")
  
def generate_top_3_resume_json_files(matches):
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed. Run: pip install openai")

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. Set it before running GPT generation.")

    candidate_truth_source = load_json(CANDIDATE_TRUTH_SOURCE_FILE)
    keyword_phrase_map = load_json(KEYWORD_PHRASE_MAP_FILE)
    top_jobs = select_top_jobs(matches, TOP_N_FOR_GPT)

    print("\n" + "=" * 90)
    print(f"GPT CUSTOM RESUME JSON GENERATION: TOP {len(top_jobs)} JOBS")
    print("=" * 90)
    

    client = OpenAI()
    saved_files = []

    for index, job in enumerate(top_jobs, start=1):
        print(f"\n[{index}/{len(top_jobs)}] Generating JSON for: {job.get('title')} ({job.get('company')})")
        resume_json = generate_custom_resume_json(
            client=client,
            job=job,
            candidate_truth_source=candidate_truth_source,
            keyword_phrase_map=keyword_phrase_map
        )
        output_path = save_custom_resume_json(job, resume_json)
        saved_files.append(str(output_path))
        print(f"    Saved: {output_path}")

    return saved_files


def collect_and_score_jobs():
    board_tokens = load_json(BOARDS_FILE)
    keywords = load_json(KEYWORDS_FILE)

    if isinstance(board_tokens, str):
        board_tokens = [board_tokens]

    all_matches = []
    content_rejects = []
    total_jobs = 0
    failed_boards = []

    print(f"\nLoaded {len(board_tokens)} board tokens.\n")

    for board_token in board_tokens:
        print(f"[+] Checking board: {board_token}")

        try:
            data = fetch_greenhouse_jobs(board_token)
            jobs = data.get("jobs", [])
            total_jobs += len(jobs)
            print(f"    Fetched {len(jobs)} jobs")

            board_matches = []
            board_content_rejects = []

            for raw_job in jobs:
                job = normalize_job(board_token, raw_job)
                include_hits, exclude_hits = match_title(job["title"], keywords)

                if include_hits and not exclude_hits and location_allowed(job["location"], job["content_text"]):
                    content_result = content_match(job, CONTENT_MAP)
                    job["include_hits"] = include_hits
                    job["exclude_hits"] = exclude_hits
                    job.update(content_result)

                    if content_result["content_decision"] in ["strong_match", "review"]:
                        board_matches.append(job)
                        all_matches.append(job)
                    else:
                        board_content_rejects.append(job)
                        content_rejects.append(job)

            print(f"    Content matches: {len(board_matches)}")
            print(f"    Content rejects: {len(board_content_rejects)}")

        except HTTPError as e:
            print(f"    HTTP error: {e.code} {e.reason}")
            failed_boards.append({"board_token": board_token, "error": str(e)})
        except URLError as e:
            print(f"    Network error: {e.reason}")
            failed_boards.append({"board_token": board_token, "error": str(e.reason)})
        except Exception as e:
            print(f"    Unexpected error: {e}")
            failed_boards.append({"board_token": board_token, "error": str(e)})

        time.sleep(0.5)

    output = {
        "summary": {
            "boards_checked": len(board_tokens),
            "total_jobs_fetched": total_jobs,
            "total_content_matches": len(all_matches),
            "total_content_rejects": len(content_rejects),
            "failed_boards": len(failed_boards),
        },
        "matches": all_matches,
        "content_rejects": content_rejects,
        "failed_boards": failed_boards,
    }

    with open(MATCHED_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 90)
    print("RUN SUMMARY")
    print("=" * 90)
    print(f"Boards checked: {len(board_tokens)}")
    print(f"Total jobs fetched: {total_jobs}")
    print(f"Total content matches: {len(all_matches)}")
    print(f"Total content rejects: {len(content_rejects)}")
    print(f"Failed boards: {len(failed_boards)}")
    print(f"Saved results to: {MATCHED_JOBS_FILE}")

    return output


def main():
    try:
        results = collect_and_score_jobs()
        saved_files = generate_top_3_resume_json_files(results.get("matches", []))

        print("\nGenerated custom resume JSON files:")
        for file_path in saved_files:
            print(f"- {file_path}")

    except FileNotFoundError as e:
        print(f"Missing required file: {e.filename}")
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
