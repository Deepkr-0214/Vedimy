import os, re, json, time, random
from collections import Counter
try:
    from rake_nltk import Rake
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
except ImportError:
    Rake, sent_tokenize, word_tokenize, stopwords = None, None, None, None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None

USE_REAL_AI = os.environ.get('USE_REAL_AI', 'false').lower() == 'true'

SUPPORTED_LANGUAGES = {
    'hi': 'Hindi', 'en': 'English', 'ta': 'Tamil', 'te': 'Telugu',
    'mr': 'Marathi', 'bn': 'Bengali', 'gu': 'Gujarati', 'kn': 'Kannada',
    'ml': 'Malayalam', 'pa': 'Punjabi', 'ur': 'Urdu', 'fr': 'French',
    'de': 'German', 'es': 'Spanish', 'ar': 'Arabic', 'zh-CN': 'Chinese (Simplified)',
    'ja': 'Japanese',
}

def clean_transcript(raw_text: str) -> str:
    fillers = ['um', 'uh', 'like', 'you know', 'basically', 'actually', 'literally']
    text = raw_text.lower()
    for f in fillers:
        text = re.sub(r'\b' + f + r'\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_summary(transcript: str) -> dict:
    start = time.time()
    
    if not sent_tokenize: # Fallback if NLTK missing
        sentences = [s.strip() + '.' for s in transcript.split('.') if len(s.strip()) > 5]
    else:
        sentences = sent_tokenize(transcript)
        sentences = [s.strip() for s in sentences if len(s.split()) > 5]
    
    summary = ' '.join(sentences[:3]) if len(sentences) >= 3 else ' '.join(sentences)
    
    signal_words = [
        'important', 'key', 'note', 'remember', 'define', 'definition',
        'first', 'second', 'third', 'finally', 'conclusion', 'therefore',
        'means', 'refers to', 'is called', 'example', 'such as'
    ]
    key_points = []
    for s in sentences:
        s_lower = s.lower()
        if any(w in s_lower for w in signal_words):
            point = s.strip().rstrip('.')
            if len(point) > 20 and point not in key_points:
                key_points.append(point)
    
    if len(key_points) < 3:
        key_points = [sentences[i].strip() for i in range(0, len(sentences), 4)][:6]
    key_points = key_points[:8]
    
    important_topics = []
    if Rake:
        r = Rake()
        r.extract_keywords_from_text(transcript)
        important_topics = r.get_ranked_phrases()[:6]
    
    top_keywords = []
    if stopwords and word_tokenize:
        stop = set(stopwords.words('english'))
        words = [w.lower() for w in word_tokenize(transcript)
                 if w.isalpha() and w.lower() not in stop and len(w) > 3]
        top_keywords = [w for w, _ in Counter(words).most_common(10)]
    
    elapsed = int((time.time() - start) * 1000)
    
    return {
        'summary': summary,
        'key_points': key_points,
        'important_topics': important_topics,
        'keywords': top_keywords,
        'processing_time_ms': elapsed,
        'sentence_count': len(sentences),
        'word_count': len(transcript.split())
    }

def translate_summary(summary: str, key_points: list, target_lang: str) -> dict:
    if target_lang == 'en':
        return {'summary': summary, 'key_points': key_points, 'language': 'en'}
    if not GoogleTranslator:
        return {'summary': summary, 'key_points': key_points, 'language': 'en', 'error': 'Translation unavailable'}
    
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated_summary = translator.translate(summary)
        translated_points = []
        for point in key_points:
            try:
                translated_points.append(translator.translate(point))
            except Exception:
                translated_points.append(point)
        
        return {
            'summary': translated_summary,
            'key_points': translated_points,
            'language': target_lang,
            'language_name': SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        }
    except Exception as e:
        return {'summary': summary, 'key_points': key_points, 'language': 'en', 'error': str(e)}

def _make_short_answer(point: str, qnum: int) -> dict:
    transformations = [
        (r'^(.+) is (.+)', r'What is \1?'),
        (r'^(.+) are (.+)', r'What are \1?'),
        (r'^(.+) means (.+)', r'What does \1 mean?'),
    ]
    question_text = None
    for pattern, replacement in transformations:
        match = re.match(pattern, point, re.IGNORECASE)
        if match:
            question_text = re.sub(pattern, replacement, point, flags=re.IGNORECASE)
            break
    if not question_text:
        question_text = f"Explain the following concept: \"{point[:80]}...\""
    
    keywords = []
    if stopwords and word_tokenize:
        stop = set(stopwords.words('english'))
        keywords = [w for w in word_tokenize(point) if w.isalpha() and w.lower() not in stop and len(w) > 3][:5]
        
    return {
        'id': qnum,
        'type': 'short_answer',
        'question': question_text,
        'model_answer': point,
        'keywords': keywords,
    }

def generate_questions(transcript: str, summary: str, key_points: list, count: int = 5, q_type: str = 'mixed', difficulty: str = 'medium') -> list:
    questions = []
    for i, point in enumerate(key_points[:count]):
        questions.append(_make_short_answer(point, i + 1))
    return questions[:count]

def extract_pdf_text(file_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    pages_text = [page.get_text('text').strip() for page in doc if page.get_text('text').strip()]
    doc.close()
    full_text = '\n\n'.join(pages_text)
    if not full_text:
        raise ValueError('PDF contains no extractable text.')
    return full_text
