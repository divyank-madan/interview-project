from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import io
import re
from PyPDF2 import PdfReader
from docx import Document
from sentence_transformers import SentenceTransformer, util
import torch

# Initialize semantic model (lazy loaded for performance)
_semantic_model = None

def get_semantic_model():
    global _semantic_model
    if _semantic_model is None:
        _semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _semantic_model

app = FastAPI(
    title="Resume Match API",
    description="Score a resume against a job description and return fit recommendations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class MatchRequest(BaseModel):
    resume: str
    job_description: str

class MatchResponse(BaseModel):
    fit: bool
    score: int
    details: str
    matched_keywords: list[str] = Field(default_factory=list)

STOP_WORDS = {
    "and", "or", "the", "a", "an", "to", "for", "in", "of", "with", "on", "as", "by",
    "at", "is", "are", "be", "has", "have", "this", "that", "from", "will", "using",
}


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def extract_keywords(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens = [token.strip() for token in normalized.split() if token.strip()]
    keywords = [token for token in tokens if token not in STOP_WORDS and len(token) > 2]
    return keywords


def extract_resume_tokens(text: str) -> set[str]:
    return set(extract_keywords(text))


def extract_section_phrases(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [phrase.strip() for phrase in re.split(r"[\.;\n]+", normalized) if phrase.strip() and len(phrase.split()) > 2]

def compute_semantic_similarity(resume_text: str, job_description_text: str) -> float:
    """
    Compute semantic similarity between resume and job description.
    Returns a score between 0 and 1.
    """
    try:
        model = get_semantic_model()
        
        # Split into sentences/paragraphs for better matching
        resume_sentences = [s.strip() for s in re.split(r'[.\n]+', resume_text) if len(s.strip()) > 10]
        jd_sentences = [s.strip() for s in re.split(r'[.\n]+', job_description_text) if len(s.strip()) > 10]
        
        if not resume_sentences or not jd_sentences:
            return 0.0
        
        # Limit to top sentences to avoid timeout on large documents
        resume_sentences = resume_sentences[:20]
        jd_sentences = jd_sentences[:20]
        
        # Encode texts
        resume_embeddings = model.encode(resume_sentences, convert_to_tensor=True)
        jd_embeddings = model.encode(jd_sentences, convert_to_tensor=True)
        
        # Compute similarity matrix
        similarity_matrix = util.pytorch_cos_sim(resume_embeddings, jd_embeddings)
        
        # Get best match for each JD sentence (max similarity)
        best_matches = torch.max(similarity_matrix, dim=0)[0]
        
        # Average the best matches
        semantic_score = torch.mean(best_matches).item()
        
        return float(semantic_score)
    except Exception as e:
        # If semantic matching fails, return 0 (won't affect keyword matching)
        print(f"Semantic matching error: {str(e)}", flush=True)
        return 0.0


def compute_global_semantic_similarity(resume_text: str, job_description_text: str) -> float:
    """
    Compute semantic similarity between entire resume and job description using pooled embeddings.
    Returns a score between 0 and 1.
    """
    try:
        model = get_semantic_model()
        # Truncate very long documents to reasonable length for encoding
        resume_excerpt = resume_text.strip()[:4000]
        jd_excerpt = job_description_text.strip()[:4000]
        if not resume_excerpt or not jd_excerpt:
            return 0.0
        emb_resume = model.encode(resume_excerpt, convert_to_tensor=True)
        emb_jd = model.encode(jd_excerpt, convert_to_tensor=True)
        sim = util.pytorch_cos_sim(emb_resume, emb_jd).item()
        return float(max(0.0, min(1.0, sim)))
    except Exception as e:
        print(f"Global semantic error: {str(e)}", flush=True)
        return 0.0


def parse_experience_years(text: str) -> int:
    matches = re.findall(r"\b(\d+)\+?\s+years?\b", text.lower())
    return int(matches[0]) if matches else 0


def read_upload_text(file: UploadFile | None) -> str:
    if not file:
        return ""

    content = file.file.read()
    file.file.seek(0)
    filename = (file.filename or "").lower()

    if filename.endswith('.pdf'):
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Unable to parse PDF file: {str(e)}")

    if filename.endswith('.docx'):
        try:
            document = Document(io.BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Unable to parse DOCX file: {str(e)}")

    try:
        text = content.decode('utf-8', errors='ignore').strip()
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read file: {str(e)}")


JOB_TITLES = {
    "intern",
    "junior",
    "mid",
    "senior",
    "lead",
    "manager",
    "director",
    "engineer",
    "developer",
    "analyst",
    "architect",
}


def score_payload(resume_text: str, job_description_text: str) -> MatchResponse:
    resume_tokens = extract_resume_tokens(resume_text)
    jd_keywords = extract_keywords(job_description_text)

    if not jd_keywords:
        return MatchResponse(
            fit=False,
            score=0,
            details="No meaningful job description keywords found.",
            matched_keywords=[],
        )

    matched_keywords = sorted(set(jd_keywords) & resume_tokens)
    missing_keywords = sorted(set(jd_keywords) - resume_tokens)
    match_ratio = len(matched_keywords) / len(set(jd_keywords))

    # Phrase matches
    phrase_matches = sum(1 for phrase in extract_section_phrases(job_description_text) if phrase in resume_text)

    # Compute both sentence-level and global semantic similarity
    sentence_semantic = compute_semantic_similarity(resume_text, job_description_text)
    global_semantic = compute_global_semantic_similarity(resume_text, job_description_text)
    semantic_score = float(max(sentence_semantic or 0.0, global_semantic or 0.0))

    # Build normalized signals (0..1)
    keyword_norm = match_ratio
    phrase_norm = min(1.0, phrase_matches / 3.0)
    combined_keyword = 0.7 * keyword_norm + 0.3 * phrase_norm

    # Convex combination: favor semantic similarity but keep keyword signal
    semantic_weight = 0.8
    combined_score = semantic_weight * semantic_score + (1 - semantic_weight) * combined_keyword

    # Base score scaled to 0-100
    score = int(round(max(0.0, min(1.0, combined_score)) * 100))

    # Small semantic boost for very high semantic alignment
    if semantic_score > 0.85 and score < 95:
        score = min(100, score + 8)

    # Aggressive boost when both semantic and keyword signals are strong
    matched_count = len(matched_keywords)
    jd_count = len(set(jd_keywords))
    keyword_norm = match_ratio
    # Require at least a reasonable number of matched keywords (absolute or relative)
    min_keyword_threshold = max(10, int(0.15 * jd_count))
    if semantic_score >= 0.55 and matched_count >= min_keyword_threshold:
        boosted = int(min(100, round(80 + semantic_score * 20 + keyword_norm * 10)))
        score = max(score, boosted)

    # (component breakdown appended later after details is initialized)

    jd_years = parse_experience_years(job_description_text)
    resume_years = parse_experience_years(resume_text)
    if jd_years and resume_years >= jd_years:
        score += 10

    jd_titles = {word for word in job_description_text.split() if word in JOB_TITLES}
    resume_titles = {word for word in resume_text.split() if word in JOB_TITLES}
    title_matches = sorted(jd_titles & resume_titles)
    if title_matches:
        score += 10

    score = min(100, score)
    fit = score >= 55

    details = []
    details.append(f"Matched {len(matched_keywords)}/{len(set(jd_keywords))} keywords.")
    if matched_keywords:
        details.append(f"Keywords found: {', '.join(matched_keywords)}.")
    if missing_keywords:
        details.append(f"Missing keywords: {', '.join(missing_keywords[:10])}{'...' if len(missing_keywords) > 10 else ''}.")
    if phrase_matches:
        details.append(f"Found {phrase_matches} matching phrase(s) from the JD.")

    # Component breakdown for tuning
    details.append(
        f"Component scores - semantic: {int(semantic_score*100)}%, keywords: {int(keyword_norm*100)}%, phrases: {int(phrase_norm*100)}%, combined: {int(round(combined_score*100))}%.")

    # Add semantic matching details
    if semantic_score > 0.65:
        details.append(f"Semantic match score: {int(semantic_score * 100)}% (very strong conceptual alignment).")
    elif semantic_score > 0.45:
        details.append(f"Semantic match score: {int(semantic_score * 100)}% (strong conceptual alignment).")
    elif semantic_score > 0.25:
        details.append(f"Semantic match score: {int(semantic_score * 100)}% (moderate conceptual alignment).")
    if jd_years:
        details.append(
            f"Experience: resume {resume_years} year(s) vs JD {jd_years} year(s)."
        )
    if title_matches:
        details.append(f"Title match: {', '.join(title_matches)}.")

    return MatchResponse(
        fit=fit,
        score=score,
        details=" ".join(details),
        matched_keywords=matched_keywords,
    )


@app.post("/score", response_model=MatchResponse)
async def score_resume(request: Request):
    content_type = request.headers.get("content-type", "")
    resume_text = ""
    job_description_text = ""
    errors = []

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        resume_text = (form.get("resume") or "").strip()
        job_description_text = (form.get("job_description") or "").strip()
        resume_file = form.get("resume_file")
        job_file = form.get("job_file")

        # Try to extract text from uploaded files
        if resume_file and hasattr(resume_file, 'file') and hasattr(resume_file, 'filename'):
            try:
                file_text = read_upload_text(resume_file)
                if file_text:
                    resume_text = file_text
                else:
                    errors.append("Resume file was uploaded but contains no readable text.")
            except HTTPException:
                raise
            except Exception as e:
                errors.append(f"Error reading resume file: {str(e)}")
        
        if job_file and hasattr(job_file, 'file') and hasattr(job_file, 'filename'):
            try:
                file_text = read_upload_text(job_file)
                if file_text:
                    job_description_text = file_text
                else:
                    errors.append("Job description file was uploaded but contains no readable text.")
            except HTTPException:
                raise
            except Exception as e:
                errors.append(f"Error reading job file: {str(e)}")
    else:
        body = await request.json()
        resume_text = (body.get("resume", "") or "").strip()
        job_description_text = (body.get("job_description", "") or "").strip()

    # Validate both fields have content
    missing = []
    if not resume_text:
        missing.append("resume")
    if not job_description_text:
        missing.append("job description")
    
    if missing or errors:
        if errors:
            detail = " ".join(errors)
        else:
            detail = f"Please provide a {' and '.join(missing)} (as text or file)."
        raise HTTPException(status_code=400, detail=detail)

    return score_payload(resume_text, job_description_text)
