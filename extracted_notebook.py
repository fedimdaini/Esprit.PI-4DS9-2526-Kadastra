# ── Dépendances NLP avancées ─────────────────────────────────────────────────
!pip install psycopg2-binary openai fpdf2 pandas tqdm spacy language-tool-python \
             python-dateutil requests peft transformers datasets accelerate bitsandbytes \
             ipywidgets sentence-transformers faiss-cpu rapidfuzz scikit-learn -q

# ── Modèles spaCy ────────────────────────────────────────────────────────────
!python -m spacy download fr_core_news_lg -q
!python -m spacy download fr_core_news_sm -q

print('✅ Installation terminée !')
print('   Nouveaux packages : sentence-transformers, faiss-cpu, rapidfuzz, scikit-learn')

import os, re, json, time, requests
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from openai import OpenAI
from tqdm import tqdm

try:
    from google.colab import userdata
    ESPRIT_API_KEY = userdata.get('ESPRIT_API_KEY')
    GROQ_API_KEY   = userdata.get('GROQ_API_KEY')
except Exception:
    ESPRIT_API_KEY = 'sk-e8d1f52f7bce4a349af80b4080b24205'
    GROQ_API_KEY   = 'GROQ_API_KEY_REMOVED'

ESPRIT_BASE_URL    = 'https://tokenfactory.esprit.tn/api'
ESPRIT_MODEL       = 'hosted_vllm/Llama-3.1-70B-Instruct'
client_llm         = OpenAI(api_key=ESPRIT_API_KEY, base_url=ESPRIT_BASE_URL)

GROQ_BASE_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_HEADERS  = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
GROQ_MODELS   = {
    'Llama-3-8B':  'llama-3.1-8b-instant',
    'Llama-3-70B': 'llama-3.3-70b-versatile',
}

DB_CONFIG = {
    'host': 'sami-scraping.duckdns.org', 'port': '5432',
    'database': 'kadastra', 'user': 'kadastra_user', 'password': 'kadastra123'
}
IMAGE_BASE_URL     = 'http://sami-scraping.duckdns.org:8081/images'
DATASET_PATH       = '/content/kadastra_training_dataset.jsonl'
BEST_MODEL_DIR     = '/content/kadastra_best_model'
BEST_MODEL_META    = '/content/kadastra_best_model_metadata.json'
BEST_LLM_META_PATH = '/content/kadastra_best_llm.json'
FAISS_INDEX_PATH   = '/content/kadastra_faiss.index'
FAISS_META_PATH    = '/content/kadastra_faiss_meta.json'

print('✅ Configuration chargée')
print(f'   ESPRIT  : {ESPRIT_MODEL}')
print(f'   Groq    : {list(GROQ_MODELS.values())}')
print(f'   ESPRIT Key : {"OK" if ESPRIT_API_KEY else "MANQUANTE ⚠️"}')
print(f'   Groq Key   : {"OK" if GROQ_API_KEY.startswith("gsk_") else "INVALIDE ⚠️"}')
def get_connection():
    return psycopg2.connect(
        host=DB_CONFIG['host'], port=DB_CONFIG['port'],
        dbname=DB_CONFIG['database'], user=DB_CONFIG['user'],
        password=DB_CONFIG['password'], connect_timeout=10
    )

try:
    conn = get_connection(); conn.close()
    print('✅ Connexion PostgreSQL réussie !')
except Exception as e:
    print(f'❌ Erreur : {e}')

def fetch_listing(listing_id=None, contract_type=None):
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if listing_id:
        cursor.execute('SELECT * FROM data WHERE id = %s;', (listing_id,))
    elif contract_type == 'terrain':
        cursor.execute("SELECT * FROM data WHERE prix IS NOT NULL AND LOWER(type) LIKE '%terrain%' ORDER BY RANDOM() LIMIT 1;")
    elif contract_type == 'location':
        cursor.execute("SELECT * FROM data WHERE prix IS NOT NULL AND (LOWER(type) LIKE '%location%' OR LOWER(titre) LIKE '%louer%') ORDER BY RANDOM() LIMIT 1;")
    else:
        cursor.execute("SELECT * FROM data WHERE prix IS NOT NULL AND LOWER(type) NOT LIKE '%terrain%' AND LOWER(type) NOT LIKE '%location%' ORDER BY RANDOM() LIMIT 1;")
    listing = cursor.fetchone()
    cursor.close(); conn.close()
    return dict(listing) if listing else None

def fetch_batch_listings(limit=10, contract_type=None):
    limit  = int(limit)
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    queries = {
        'terrain':  ("SELECT * FROM data WHERE prix IS NOT NULL AND LOWER(type) LIKE %s ORDER BY RANDOM() LIMIT %s;", ('%terrain%', limit)),
        'location': ("SELECT * FROM data WHERE prix IS NOT NULL AND (LOWER(type) LIKE %s OR LOWER(titre) LIKE %s) ORDER BY RANDOM() LIMIT %s;", ('%location%', '%louer%', limit)),
        'vente':    ("SELECT * FROM data WHERE prix IS NOT NULL AND LOWER(type) NOT LIKE %s AND LOWER(type) NOT LIKE %s ORDER BY RANDOM() LIMIT %s;", ('%terrain%', '%location%', limit)),
    }
    sql, params = queries.get(contract_type, ('SELECT * FROM data WHERE prix IS NOT NULL ORDER BY RANDOM() LIMIT %s;', (limit,)))
    cursor.execute(sql, params)
    listings = [dict(row) for row in cursor.fetchall()]
    cursor.close(); conn.close()
    return listings

listing = fetch_listing()
if listing:
    print(f'✅ Annonce test récupérée : ID={listing.get("id")} | {listing.get("titre","")[:60]}')

def explore_database():
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute('SELECT COUNT(*) as total FROM data;')
    print(f"Total annonces : {cursor.fetchone()['total']}")
    sql = (
        "SELECT COUNT(*) FILTER (WHERE LOWER(type) LIKE '%terrain%') as terrains,"
        " COUNT(*) FILTER (WHERE LOWER(type) LIKE '%location%' OR LOWER(titre) LIKE '%louer%') as locations,"
        " COUNT(*) as total FROM data WHERE prix IS NOT NULL;"
    )
    cursor.execute(sql)
    cats = cursor.fetchone()
    print(f"Ventes≈{cats['total']-cats['locations']-cats['terrains']} | Locations={cats['locations']} | Terrains={cats['terrains']}")
    cursor.close(); conn.close()

explore_database()

import spacy
import language_tool_python
from rapidfuzz import fuzz, process as rfprocess

# ── Chargement modèle ────────────────────────────────────────────────────────
try:
    nlp = spacy.load('fr_core_news_lg')
    print('✅ spaCy fr_core_news_lg chargé')
except Exception:
    nlp = spacy.load('fr_core_news_sm')
    print('⚠️  Fallback fr_core_news_sm')

# ── Règles d'entités personnalisées pour l'immobilier tunisien ───────────────
# Ces patterns étendent le NER standard avec des entités spécifiques
# au domaine immobilier et géographique tunisien
from spacy.pipeline import EntityRuler

# Supprimer le ruler existant s'il y en a un (pour re-run)
if 'kadastra_ruler' in nlp.pipe_names:
    nlp.remove_pipe('kadastra_ruler')

ruler = nlp.add_pipe('entity_ruler', name='kadastra_ruler', before='ner')

# Gouvernorats et villes tunisiennes (GPE/LOC)
TUNISIAN_LOCATIONS = [
    'Tunis', 'Sfax', 'Sousse', 'Kairouan', 'Bizerte', 'Gabès',
    'Ariana', 'Gafsa', 'Monastir', 'Ben Arous', 'Kasserine', 'Médenine',
    'Nabeul', 'Tataouine', 'Béja', 'Jendouba', 'Mahdia', 'Sidi Bouzid',
    'Siliana', 'Kébili', 'Le Kef', 'Tozeur', 'Manouba', 'Zaghouan',
    'La Marsa', 'Carthage', 'Sidi Bou Saïd', 'Hammamet', 'Nabeul',
    'Djerba', 'Zarzis', 'Tabarka', 'Ain Draham', 'El Aouina',
]

# Types de biens immobiliers spécifiques (PROPERTY)
RE_PROPERTY_TYPES = [
    'villa', 'appartement', 'maison', 'duplex', 'studio', 'S+1', 'S+2',
    'S+3', 'S+4', 'S+5', 'bungalow', 'ferme', 'local commercial',
    'bureau', 'entrepôt', 'hangar', 'titre foncier', 'terrain agricole',
    'terrain constructible', 'lot de terrain', 'parcelle',
]

# Documents légaux tunisiens (LEGAL_DOC)
LEGAL_DOCS = [
    'titre foncier', 'COC', 'code des obligations', 'loi 77-40',
    'loi 90-17', 'code civil tunisien', 'registre foncier',
    'attestation de propriété', 'acte de vente', 'promesse de vente',
    'contrat de bail', 'compromis de vente',
]

patterns = []
for loc in TUNISIAN_LOCATIONS:
    patterns.append({'label': 'LOC', 'pattern': loc})
    patterns.append({'label': 'LOC', 'pattern': loc.lower()})
for prop in RE_PROPERTY_TYPES:
    patterns.append({'label': 'PROPERTY', 'pattern': prop})
    patterns.append({'label': 'PROPERTY', 'pattern': [{'LOWER': w.lower()} for w in prop.split()]})
for doc in LEGAL_DOCS:
    patterns.append({'label': 'LEGAL_DOC', 'pattern': doc})
    patterns.append({'label': 'LEGAL_DOC', 'pattern': [{'LOWER': w.lower()} for w in doc.split()]})

ruler.add_patterns(patterns)
print(f'✅ EntityRuler ajouté : {len(patterns)} patterns domaine immobilier tunisien')
print(f'   Entités custom : LOC (gouvernorats), PROPERTY (biens), LEGAL_DOC (documents)')
print(f'   Pipeline : {nlp.pipe_names}')

# ── Dictionnaire légal enrichi avec synonymes ────────────────────────────────
LEGAL_DICTIONARY_FR = {
    'payer': 'régler', 'paiement': 'remise de fonds', 'accord': 'convention',
    'contrat': 'acte sous seing privé', 'propriétaire': 'bailleur / vendeur',
    'acheteur': 'acquéreur', 'locataire': 'preneur à bail',
    'loyer': 'redevance mensuelle', 'caution': 'dépôt de garantie',
    'fin': 'résiliation', 'annuler': 'résoudre', 'problème': 'litige',
    'tribunal': 'juridiction compétente', 'loi': 'disposition légale',
    'droit': 'prérogative', 'devoir': 'obligation',
    'signature': "apposition de la griffe", 'date': "date de prise d'effet",
    'adresse': 'domicile élu', 'identité': 'désignation civile',
    'terrain': 'parcelle foncière', 'maison': "immeuble à usage d'habitation",
    'appartement': "fraction d'immeuble en copropriété",
    'villa': 'résidence individuelle', 'prix': 'contrepartie financière',
    'vente': 'cession immobilière', 'achat': 'acquisition immobilière',
    'garantie': 'garantie contractuelle', 'défaut': 'vice caché',
    'frais': 'charges accessoires', 'taxe': 'imposition fiscale',
    'notaire': 'officier ministériel', 'litige': 'différend juridique',
    'surface': 'superficie en mètres carrés',
    # Termes spécifiques tunisiens
    'titre foncier': 'titre de propriété foncière immatriculé',
    'moudawana': 'code du statut personnel',
    'recette des finances': 'bureau de perception fiscale',
    'immatriculer': 'inscrire au registre foncier',
    'cadastre': 'service du cadastre et des finances',
}

# ── Expansion fuzzy : trouver des variantes orthographiques ─────────────────
# Exemple : "locateur" → "locataire", "acquereur" → "acquéreur"
LEGAL_KEYS = list(LEGAL_DICTIONARY_FR.keys())

def fuzzy_legal_lookup(word, threshold=82):
    '''
    Retourne le terme légal correspondant si le mot est proche d'une clé
    du dictionnaire (distance Levenshtein normalisée >= threshold%).
    Permet de gérer les fautes de frappe et variantes orthographiques.
    '''
    word_lower = word.lower()
    # Correspondance exacte d'abord
    if word_lower in LEGAL_DICTIONARY_FR:
        return LEGAL_DICTIONARY_FR[word_lower], 100
    # Fuzzy matching sur les clés
    best_match = rfprocess.extractOne(
        word_lower, LEGAL_KEYS,
        scorer=fuzz.ratio,
        score_cutoff=threshold
    )
    if best_match:
        matched_key, score, _ = best_match
        return LEGAL_DICTIONARY_FR[matched_key], score
    return None, 0

def transform_to_legal_terms_advanced(text):
    '''
    Transformation lexicale améliorée :
    1. Segmentation par spaCy (doc.sents)
    2. Lemmatisation token par token
    3. Lookup exact dans le dictionnaire légal
    4. Fallback fuzzy pour variantes orthographiques
    5. Préservation de la casse d'origine
    '''
    doc = nlp(text)
    result_sentences = []
    replacements_log = []

    for sent in doc.sents:
        tokens_out = []
        for token in sent:
            if token.is_space or token.is_punct:
                tokens_out.append(token.text)
                continue

            lemma = token.lemma_.lower()
            orig  = token.text

            # 1. Lookup exact sur lemme
            legal_exact = LEGAL_DICTIONARY_FR.get(lemma)
            if legal_exact:
                tokens_out.append(legal_exact)
                replacements_log.append((orig, legal_exact, 'exact', 100))
                continue

            # 2. Lookup exact sur texte brut
            legal_raw = LEGAL_DICTIONARY_FR.get(orig.lower())
            if legal_raw:
                tokens_out.append(legal_raw)
                replacements_log.append((orig, legal_raw, 'exact_raw', 100))
                continue

            # 3. Fuzzy fallback (seulement pour mots ≥ 5 chars, pas de stopwords)
            if not token.is_stop and len(orig) >= 5:
                legal_fuzzy, score = fuzzy_legal_lookup(lemma)
                if legal_fuzzy and score >= 85:
                    tokens_out.append(legal_fuzzy)
                    replacements_log.append((orig, legal_fuzzy, 'fuzzy', score))
                    continue

            tokens_out.append(orig)

        sentence = ' '.join(tokens_out).strip()
        if sentence:
            result_sentences.append(sentence.capitalize())

    return ' '.join(result_sentences), replacements_log

# Test
test_phrases = [
    "L'acheteur doit payer le prix au vendeur.",
    "Le locateur a signé l'accord de location.",
    "Les propiétaires annuleront le contrat en cas de défaut.",
]
print('Démonstration transform_to_legal_terms_advanced :')
for phrase in test_phrases:
    result, logs = transform_to_legal_terms_advanced(phrase)
    print(f'  Original   : {phrase}')
    print(f'  Transformé : {result}')
    if logs:
        for orig, legal, method, score in logs:
            print(f'    [{method} {score}%] "{orig}" → "{legal}"')
    print()

# ── POS utilisé pour 3 choses concrètes ────────────────────────────────────
# 1. Filtrer les entités NER par POS (éviter les faux positifs)
# 2. Extraire les verbes d'obligation modaux (doit, peut, interdit, etc.)
# 3. Enrichir le prompt LLM avec les obligations détectées

OBLIGATION_PATTERNS = {
    'obligation_positive': ['doit', 'devra', 'est tenu', 'est obligé', "s'engage", "s'oblige"],
    'obligation_negative': ['ne doit pas', 'est interdit', 'ne peut pas', 'est défendu', 'ne saurait'],
    'permission':          ['peut', 'pourra', 'est autorisé', 'a le droit', 'est en droit'],
    'condition':           ['si', 'en cas de', 'sous réserve', 'à condition', 'sauf si'],
}

def extract_obligations_from_text(text):
    doc = nlp(text)
    obligations = []
    for sent in doc.sents:
        sent_text_lower = sent.text.lower()
        for ob_type, patterns_list in OBLIGATION_PATTERNS.items():
            for pat in patterns_list:
                if pat in sent_text_lower:
                    subject = None
                    for token in sent:
                        if token.dep_ in ('nsubj', 'nsubj:pass') and token.pos_ in ('NOUN', 'PROPN', 'PRON'):
                            subject = token.lemma_
                            break
                    obligations.append({
                        'type':    ob_type,
                        'pattern': pat,
                        'clause':  sent.text.strip()[:120],
                        'subject': subject or 'inconnu'
                    })
                    break
    return obligations

def extract_entities_advanced(listing):
    text_fields = [
        str(listing.get('titre',        '') or ''),
        str(listing.get('description',  '') or ''),
        str(listing.get('localisation', '') or ''),
        str(listing.get('adresse',      '') or ''),
    ]
    full_text = ' '.join([t for t in text_fields if t.strip()])
    doc = nlp(full_text)

    entities = {
        'lieux':              [],
        'dates':              [],
        'montants':           [],
        'personnes':          [],
        'organisations':      [],
        'biens':              [],
        'docs_legaux':        [],
        'noun_chunks_scored': [],
        'lemmes_cles':        [],
        'obligations':        [],
        'verbes_cles':        [],
    }

    for ent in doc.ents:
        raw   = ent.text.strip()
        lemma = ent.lemma_.strip()
        if not raw:
            continue
        pos_ok = True
        if ent.label_ in ('LOC', 'GPE') and ent.root.pos_ not in ('PROPN', 'NOUN'):
            pos_ok = False
        if ent.label_ == 'PER' and ent.root.pos_ != 'PROPN':
            pos_ok = False
        if not pos_ok:
            continue
        if ent.label_ in ('LOC', 'GPE', 'LOCATION'):
            entities['lieux'].append(lemma or raw)
        elif ent.label_ in ('DATE', 'TIME'):
            entities['dates'].append(raw)
        elif ent.label_ in ('MONEY', 'CARDINAL', 'QUANTITY'):
            entities['montants'].append(raw)
        elif ent.label_ in ('PER', 'PERSON'):
            entities['personnes'].append(raw)
        elif ent.label_ == 'ORG':
            entities['organisations'].append(raw)
        elif ent.label_ == 'PROPERTY':
            entities['biens'].append(raw)
        elif ent.label_ == 'LEGAL_DOC':
            entities['docs_legaux'].append(raw)

    entities['obligations'] = extract_obligations_from_text(full_text)

    seen_verbs = set()
    for token in doc:
        if token.pos_ == 'VERB' and not token.is_stop and token.dep_ not in ('aux', 'aux:pass'):
            lemma_v = token.lemma_.lower()
            if lemma_v not in seen_verbs and len(lemma_v) > 3:
                entities['verbes_cles'].append(lemma_v)
                seen_verbs.add(lemma_v)

    seen_lemmas = set()
    for token in doc:
        if token.pos_ in ('NOUN', 'PROPN') and not token.is_stop and len(token.text) > 3:
            lemma = token.lemma_.lower()
            if lemma not in seen_lemmas:
                entities['lemmes_cles'].append(lemma)
                seen_lemmas.add(lemma)

    # ── Déduplication — obligations ignorées car contient des dicts ──────────
    for key in entities:
        if isinstance(entities[key], list) and key != 'obligations':
            entities[key] = list(dict.fromkeys(entities[key]))

    return entities

# Test sur listing
if listing:
    ents = extract_entities_advanced(listing)
    print('=== NER avancé + POS filtrage ===')
    for label, vals in ents.items():
        if vals and label != 'obligations':
            print(f'   {label:20s} : {vals[:4]}')
    if ents['obligations']:
        print(f'   obligations (ex) : {ents["obligations"][0]}')
from sklearn.feature_extraction.text import TfidfVectorizer
import math

# ── Corpus de référence juridique (domaine immobilier tunisien) ───────────────
# Ce corpus est utilisé pour calculer l'IDF des termes juridiques.
# Les termes fréquents dans ce corpus auront un IDF faible (peu informatifs),
# les termes rares (spécifiques) auront un IDF élevé.

LEGAL_CORPUS_REF = [
    "Le vendeur cède la propriété immobilière à l'acquéreur selon le code des obligations",
    "Le bailleur met à disposition du locataire le bien immobilier loué contre redevance",
    "La superficie du terrain est de cent mètres carrés situé à Tunis Gouvernorat",
    "Le titre foncier immatriculé garantit la propriété conformément à la loi tunisienne",
    "Le prix de vente est fixé en dinars tunisiens payable par virement bancaire",
    "Le contrat de bail est conclu pour une durée d'un an renouvelable",
    "Le dépôt de garantie équivaut à trois mois de loyer remboursable à la résiliation",
    "Les charges d'enregistrement et les droits fonciers sont à la charge de l'acquéreur",
    "Le tribunal de première instance est compétent pour tout litige immobilier",
    "La parcelle foncière est délimitée par des bornes cadastrales officielles",
    "L'hypothèque grevant l'immeuble doit être levée avant la signature de l'acte",
    "La garantie d'éviction protège l'acquéreur contre les revendications de tiers",
]

# Entraînement du vectoriseur TF-IDF sur le corpus légal
tfidf_vectorizer = TfidfVectorizer(
    analyzer='word',
    ngram_range=(1, 3),   # Unigrammes + bigrammes + trigrammes
    min_df=1,
    max_features=500,
    sublinear_tf=True,    # log(1+tf) pour atténuer les fréquences extrêmes
)
tfidf_vectorizer.fit(LEGAL_CORPUS_REF)
tfidf_vocab = set(tfidf_vectorizer.get_feature_names_out())
print(f'✅ TF-IDF vectoriseur entraîné : {len(tfidf_vocab)} termes')

def score_noun_chunk(chunk_text, tfidf_vectorizer, tfidf_vocab):
    '''
    Score de pertinence juridique d'un syntagme nominal.
    Combinaison de :
    - Présence dans le vocabulaire TF-IDF (0 ou 1)
    - Score TF-IDF moyen des mots du chunk
    - Bonus si contient un terme du dictionnaire légal
    - Pénalité pour les chunks trop courts (< 2 mots)
    '''
    words = chunk_text.lower().split()
    if len(words) < 2:
        return 0.0

    # Score TF-IDF des mots individuels
    tfidf_scores = []
    for word in words:
        if word in tfidf_vocab:
            tfidf_scores.append(1.0)
        else:
            tfidf_scores.append(0.0)
    tfidf_score = sum(tfidf_scores) / len(words) if words else 0.0

    # Bonus dictionnaire légal
    legal_bonus = 0.3 if any(w in LEGAL_DICTIONARY_FR for w in words) else 0.0

    # Bonus présence Tunisie/immobilier
    domain_bonus = 0.2 if any(loc.lower() in chunk_text.lower() for loc in ['tunis', 'sfax', 'sousse', 'terrain', 'titre foncier', 'appartement', 'villa']) else 0.0

    return round(min(1.0, tfidf_score + legal_bonus + domain_bonus), 3)

def extract_ranked_noun_chunks(doc, top_n=8, min_score=0.1):
    '''
    Extrait et classe les syntagmes nominaux par pertinence juridique.
    Retourne les top_n chunks avec leur score.
    '''
    LEGAL_NOUNS = {
        'maison', 'villa', 'appartement', 'terrain', 'lot', 'parcelle',
        'superficie', 'surface', 'chambre', 'pièce', 'étage', 'garage',
        'jardin', 'piscine', 'prix', 'loyer', 'caution', 'charge',
        'syndic', 'copropriété', 'titre', 'foncier', 'cadastre',
        'bien', 'propriété', 'immeuble', 'logement', 'résidence',
    }
    scored_chunks = []
    seen = set()

    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        root_lemma  = chunk.root.lemma_.lower()

        if chunk_text.lower() in seen:
            continue
        if len(chunk_text.split()) < 2:
            continue

        score = score_noun_chunk(chunk_text, tfidf_vectorizer, tfidf_vocab)

        # Boost si la racine est un nom légal connu
        if root_lemma in LEGAL_NOUNS:
            score = min(1.0, score + 0.25)

        if score >= min_score:
            scored_chunks.append({'text': chunk_text, 'score': score, 'root': root_lemma})
            seen.add(chunk_text.lower())

    scored_chunks.sort(key=lambda x: x['score'], reverse=True)
    return scored_chunks[:top_n]

# Test
if listing:
    test_text = ' '.join([str(listing.get(k,'') or '') for k in ['titre','description','adresse']])
    doc_test   = nlp(test_text[:1000])
    ranked     = extract_ranked_noun_chunks(doc_test)
    print('=== Noun chunks classés par TF-IDF juridique ===')
    for c in ranked[:6]:
        print(f'   score={c["score"]:.3f}  "{c["text"]}" (root={c["root"]})')

tool = language_tool_python.LanguageTool('fr')
print('✅ LanguageTool (fr) chargé')

GRAMMAR_FIXES_FR = [
    (r'(?i)du moi',      'du mois'),
    (r'(?i)au moi',      'au mois'),
    (r'(?i)chaque moi',  'chaque mois'),
    (r'(?i)par moi',     'par mois'),
    (r'(?i)loier',       'loyer'),
    (r'(?i)causion',     'caution'),
    (r'(?i)addresse',    'adresse'),
    (r'(?i)resiliation', 'résiliation'),
    (r'(?i)bailleure?',  'bailleur'),
    (r'(?i)acquereur',   'acquéreur'),
    (r'(?i)propiétaire', 'propriétaire'),
    (r'(?i)vendreur',    'vendeur'),
]

def correct_text_enhanced(text):
    '''Correction LanguageTool + regex sur le texte fourni.'''
    doc = nlp(text[:3000])  # Limiter pour performance
    corrected_sents = []
    for sent in doc.sents:
        s = sent.text.strip()
        if not s:
            continue
        matches   = tool.check(s)
        corrected = language_tool_python.utils.correct(s, matches)
        corrected_sents.append(corrected)
    result = ' '.join(corrected_sents)
    for pattern, replacement in GRAMMAR_FIXES_FR:
        result = re.sub(pattern, replacement, result)
    return result

def post_correct_contract(contract_text, max_chars=6000):
    '''
    NOUVEAU : correction grammaticale appliquée sur le contrat généré.
    Traite par blocs pour éviter les timeouts LanguageTool.
    '''
    if len(contract_text) <= max_chars:
        return correct_text_enhanced(contract_text)

    # Découpage par paragraphes pour les longs contrats
    paragraphs = contract_text.split('\n')
    corrected_parts = []
    buffer = ''
    for para in paragraphs:
        if len(buffer) + len(para) < 2000:
            buffer += para + '\n'
        else:
            if buffer.strip():
                corrected_parts.append(correct_text_enhanced(buffer))
            buffer = para + '\n'
    if buffer.strip():
        corrected_parts.append(correct_text_enhanced(buffer))
    return '\n'.join(corrected_parts)

print('✅ post_correct_contract() défini — sera appelé après chaque génération LLM')

# Test
test_input = "Le locateur doit paye le loier avant le dix du moi."
print(f'  Input    : {test_input}')
print(f'  Corrigé  : {correct_text_enhanced(test_input)}')

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# ── Chargement du modèle d'embeddings ────────────────────────────────────────
# paraphrase-multilingual-MiniLM-L12-v2 : multilingue, léger, bon pour le français
print('Chargement du modèle sentence-transformers...')
embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
print('✅ Modèle sentence-transformers chargé (dim=384)')

# ── Base de connaissance légale tunisienne (chunks) ───────────────────────────
# Chaque chunk représente une clause ou un article légal.
# La recherche vectorielle trouvera les chunks les plus proches
# de la requête utilisateur (sémantiquement, pas juste lexicalement).

LEGAL_CHUNKS = [
    # COC — Contrat de vente
    {"id": "coc_565", "type": "vente", "article": "Art. 565 COC",
     "text": "Le contrat de vente immobilière doit identifier les deux parties : nom, prénom, CIN et adresse complète du vendeur et de l'acquéreur."},
    {"id": "coc_567", "type": "vente", "article": "Art. 567 COC",
     "text": "La description du bien vendu doit inclure : gouvernorat, délégation, superficie en m², numéro de titre foncier."},
    {"id": "coc_568", "type": "vente", "article": "Art. 568 COC",
     "text": "Le prix de vente doit être stipulé en dinars tunisiens en chiffres et en lettres. Les pénalités de retard sont de 8% par an."},
    {"id": "coc_569", "type": "vente", "article": "Art. 569 COC",
     "text": "Le transfert de propriété est effectif à la date convenue. La remise des clés matérialise la prise de possession."},
    {"id": "coc_641", "type": "vente", "article": "Art. 641-670 COC",
     "text": "Le vendeur garantit l'acquéreur contre l'éviction et les vices cachés. La garantie décennale s'applique aux constructions."},
    {"id": "coc_frais", "type": "vente", "article": "Droits d'enregistrement",
     "text": "Les droits d'enregistrement sont de 3% du prix de vente. Les honoraires notariaux varient entre 1 et 2%."},
    # Loi 77-40 — Bail
    {"id": "loi7740_id", "type": "location", "article": "Loi 77-40 Art. 1",
     "text": "Le contrat de bail identifie le bailleur et le locataire par nom, CIN et adresse. Le bien loué est décrit avec superficie et équipements."},
    {"id": "loi7740_dur", "type": "location", "article": "Loi 77-40 Art. 5",
     "text": "La durée du bail est fixée par les parties. Le préavis de résiliation est de 3 mois minimum. Le loyer est payable du 1er au 10 du mois."},
    {"id": "loi7740_dep", "type": "location", "article": "Loi 77-40 Art. 8",
     "text": "Le dépôt de garantie ne peut excéder 3 mois de loyer. Il est restitué dans les 30 jours suivant la restitution des clés."},
    {"id": "loi7740_obl", "type": "location", "article": "Loi 77-40 Art. 12",
     "text": "Le locataire est tenu d'user du bien en bon père de famille. La sous-location est interdite sans accord écrit du bailleur."},
    {"id": "loi7740_rep", "type": "location", "article": "Loi 77-40 Art. 15",
     "text": "Le bailleur est responsable des grosses réparations. Le locataire assure l'entretien courant du bien."},
    # Terrain
    {"id": "terr_cadastre", "type": "terrain", "article": "Code foncier",
     "text": "Tout contrat portant sur un terrain doit mentionner le numéro de titre foncier immatriculé au registre foncier national."},
    {"id": "terr_nature", "type": "terrain", "article": "Code de l'urbanisme",
     "text": "La nature du terrain (agricole ou constructible) doit être précisée avec le statut urbanistique et les servitudes éventuelles."},
    {"id": "terr_bornes", "type": "terrain", "article": "Code foncier Art. 22",
     "text": "Les limites du terrain sont définies par des bornes cadastrales. Les droits de passage et servitudes grèvent le titre."},
    {"id": "terr_hyp", "type": "terrain", "article": "COC Art. 200",
     "text": "Le vendeur garantit que le terrain est libre de toute hypothèque, saisie ou droit réel non déclaré."},
    # Général
    {"id": "gen_enreg", "type": "general", "article": "Administration fiscale",
     "text": "Tout contrat immobilier doit être enregistré à la recette des finances dans les 30 jours de sa signature."},
    {"id": "gen_jur", "type": "general", "article": "Compétence judiciaire",
     "text": "Le Tribunal de Première Instance du lieu de situation du bien est compétent pour tout litige immobilier."},
    {"id": "gen_force", "type": "general", "article": "COC Art. 230",
     "text": "Le contrat fait loi entre les parties. Toute modification doit faire l'objet d'un avenant signé des deux parties."},
]

# ── Construction de l'index FAISS ────────────────────────────────────────────
chunk_texts = [c['text'] for c in LEGAL_CHUNKS]
print(f'Encodage de {len(chunk_texts)} chunks légaux...')
embeddings = embedder.encode(chunk_texts, show_progress_bar=False)
embeddings = np.array(embeddings, dtype='float32')

# Normalisation L2 pour la recherche par cosine similarity
faiss.normalize_L2(embeddings)

# Index FlatIP (produit scalaire = cosine après normalisation)
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)
print(f'✅ Index FAISS construit : {index.ntotal} vecteurs, dim={embeddings.shape[1]}')

def semantic_legal_search(query, contract_type=None, top_k=4):
    '''
    Recherche sémantique dans la base légale tunisienne.
    Retourne les top_k chunks les plus pertinents pour la requête.
    '''
    query_vec = embedder.encode([query], show_progress_bar=False)
    query_vec = np.array(query_vec, dtype='float32')
    faiss.normalize_L2(query_vec)

    scores, indices = index.search(query_vec, top_k * 2)  # Récupérer plus pour filtrer

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = LEGAL_CHUNKS[idx]
        # Filtre optionnel par type de contrat
        if contract_type and chunk['type'] not in (contract_type, 'general'):
            continue
        results.append({**chunk, 'similarity': round(float(score), 4)})
        if len(results) >= top_k:
            break
    return results

def build_rag_context(query, contract_type, top_k=4):
    '''Construit le contexte RAG vectoriel pour le LLM.'''
    chunks = semantic_legal_search(query, contract_type, top_k)
    if not chunks:
        return ''
    context_lines = ['RÉFÉRENCES LÉGALES (RAG sémantique) :']
    for c in chunks:
        context_lines.append(f'[{c["article"]} | sim={c["similarity"]:.2f}] {c["text"]}')
    return '\n'.join(context_lines)

# Sauvegarde de l'index
faiss.write_index(index, FAISS_INDEX_PATH)
with open(FAISS_META_PATH, 'w') as f:
    json.dump(LEGAL_CHUNKS, f, ensure_ascii=False, indent=2)
print(f'   Index sauvegardé : {FAISS_INDEX_PATH}')

# Test de recherche sémantique
test_query = "titre foncier terrain superficie bornes cadastrales"
results = semantic_legal_search(test_query, 'terrain', top_k=3)
print(f'\nTest recherche : "{test_query}"')
for r in results:
    print(f'  sim={r["similarity"]:.3f} | {r["article"]} : {r["text"][:70]}...')

def validate_contract_nlp(contract_text, contract_type='vente'):
    '''
    Validation NLP du contrat généré — va bien au-delà du simple keyword match.

    Analyse :
    1. Présence des entités critiques (parties, lieux, montants) via NER
    2. Clauses obligatoires via NER + recherche sémantique
    3. Obligations légales : doit / est tenu / s'engage (dépendances syntaxiques)
    4. Cohérence des montants (DT présent, chiffres cohérents)
    5. Vérification des articles légaux cités (COC, Loi 77-40, etc.)
    '''
    doc = nlp(contract_text[:5000])
    report = {
        'contract_type':      contract_type,
        'nlp_entities':       {},
        'clauses_nlp':        {},
        'obligations_found':  [],
        'legal_refs_found':   [],
        'amount_check':       {},
        'parties_check':      {},
        'score_nlp':          0,
        'max_score_nlp':      0,
        'issues':             [],
        'strengths':          [],
    }

    # 1. Extraction NER du contrat généré
    parties   = [e.text for e in doc.ents if e.label_ in ('PER', 'PERSON')]
    lieux     = [e.text for e in doc.ents if e.label_ in ('LOC', 'GPE')]
    montants  = [e.text for e in doc.ents if e.label_ in ('MONEY', 'CARDINAL', 'QUANTITY')]
    legal_docs= [e.text for e in doc.ents if e.label_ == 'LEGAL_DOC']
    biens     = [e.text for e in doc.ents if e.label_ == 'PROPERTY']

    report['nlp_entities'] = {
        'parties':    parties[:5],
        'lieux':      lieux[:5],
        'montants':   montants[:5],
        'legal_docs': legal_docs[:3],
        'biens':      biens[:3],
    }

    # 2. Clauses obligatoires (NER + keywords sémantiques)
    contract_lower = contract_text.lower()
    clause_checks = {
        'vente': {
            'Identification parties':     bool(parties) or any(k in contract_lower for k in ['vendeur','acheteur','acquéreur','cin']),
            'Description bien':           bool(biens) or any(k in contract_lower for k in ['superficie','m²','adresse']),
            'Prix stipulé':               bool(montants) or any(k in contract_lower for k in ['prix','dinars','dt']),
            'Titre foncier':              bool(legal_docs) or 'titre foncier' in contract_lower,
            'Garanties':                  any(k in contract_lower for k in ['garantie','vice','éviction']),
            'Droits enregistrement':      any(k in contract_lower for k in ['enregistrement','3%','fiscale']),
            'Juridiction':                any(k in contract_lower for k in ['tribunal','juridiction']),
            'Signature':                  any(k in contract_lower for k in ['signature','signé','seing']),
        },
        'location': {
            'Identification parties':     bool(parties) or any(k in contract_lower for k in ['bailleur','locataire','cin']),
            'Description bien':           bool(biens) or any(k in contract_lower for k in ['superficie','adresse','bien loué']),
            'Loyer':                      bool(montants) or any(k in contract_lower for k in ['loyer','dinars','redevance']),
            'Durée bail':                 any(k in contract_lower for k in ['durée','mois','an','terme']),
            'Dépôt garantie':             any(k in contract_lower for k in ['garantie','dépôt','caution']),
            'Obligations locataire':      any(k in contract_lower for k in ['obligation','interdit','usage','sous-location']),
            'Résiliation':                any(k in contract_lower for k in ['résiliation','préavis','tribunal']),
            'Signature':                  any(k in contract_lower for k in ['signature','signé','seing']),
        },
        'terrain': {
            'Identification parties':     bool(parties) or any(k in contract_lower for k in ['vendeur','acheteur','acquéreur','cin']),
            'Description terrain':        any(k in contract_lower for k in ['terrain','superficie','parcelle','hectare']),
            'Titre foncier / cadastre':   bool(legal_docs) or any(k in contract_lower for k in ['titre foncier','cadastre','immatriculé']),
            'Nature terrain':             any(k in contract_lower for k in ['agricole','constructible','nature','usage']),
            'Prix':                       bool(montants) or any(k in contract_lower for k in ['prix','dinars','contrepartie']),
            'Libre hypothèques':          any(k in contract_lower for k in ['hypothèque','libre','saisie','réel']),
            'Garanties':                  any(k in contract_lower for k in ['garantie','éviction','vice']),
            'Juridiction':                any(k in contract_lower for k in ['tribunal','juridiction']),
        },
    }
    selected_clauses = clause_checks.get(contract_type, clause_checks['vente'])
    report['clauses_nlp'] = selected_clauses
    clauses_ok = sum(selected_clauses.values())
    clauses_total = len(selected_clauses)

    # 3. Obligations légales via dépendances syntaxiques
    obligations = extract_obligations_from_text(contract_text[:3000])
    report['obligations_found'] = obligations[:5]
    has_obligations = len(obligations) >= 3  # Un bon contrat a >= 3 obligations

    # 4. Références légales citées (articles COC, lois)
    legal_ref_patterns = [
        r'art(?:icle)?\.?\s*\d+\s+(?:coc|cod)',
        r'loi\s+(?:n°\s*)?\d+[-–]\d+',
        r'code\s+des\s+obligations',
        r'décret(?:-loi)?\s+\d+',
        r'art(?:icle)?\.?\s+\d+',
    ]
    legal_refs = []
    for pat in legal_ref_patterns:
        found = re.findall(pat, contract_text.lower())
        legal_refs.extend(found[:2])
    report['legal_refs_found'] = list(set(legal_refs))[:6]
    has_legal_refs = len(legal_refs) >= 2

    # 5. Vérification des montants (cohérence DT + chiffres)
    amounts_in_text = re.findall(r'\d[\d\s,.]*(?:dt|dinar|dinars)', contract_text.lower())
    amount_in_letters = bool(re.search(r'(?:mille|cent|vingt|trente|quarante|cinquante|soixante|dix|onze|douze)\s+dinars', contract_text.lower()))
    report['amount_check'] = {
        'amounts_found':    amounts_in_text[:4],
        'amount_in_letters': amount_in_letters,
        'ok': bool(amounts_in_text),
    }

    # 6. Parties identifiées par NER
    has_two_parties = len(set(parties)) >= 2
    report['parties_check'] = {
        'parties_found': parties[:4],
        'has_two_parties': has_two_parties,
    }

    # ── Scoring NLP ────────────────────────────────────────────────────────────
    score = 0
    max_score = clauses_total + 5

    score += clauses_ok
    if has_obligations:      score += 1
    if has_legal_refs:       score += 1
    if report['amount_check']['ok']: score += 1
    if has_two_parties:      score += 1
    if amount_in_letters:    score += 1

    report['score_nlp']     = score
    report['max_score_nlp'] = max_score
    report['ccr_nlp']       = round(score / max_score * 100, 1)

    # ── Issues et Strengths ───────────────────────────────────────────────────
    for clause_name, present in selected_clauses.items():
        if not present:
            report['issues'].append(f'Clause manquante : {clause_name}')
        else:
            report['strengths'].append(f'✓ {clause_name}')
    if not has_obligations:
        report['issues'].append('Moins de 3 obligations légales détectées')
    if not has_legal_refs:
        report['issues'].append('Aucune référence à un article de loi')
    if not has_two_parties:
        report['issues'].append('Moins de 2 parties identifiées par NER')

    return report

print('✅ validate_contract_nlp() défini — validation NLP complète du contrat généré')

USER_PERMISSIONS = {
    # ── Particuliers — permissions différentes selon acheteur ou vendeur ───────
    'particulier_acheteur': {
        'vente':    ['description_bien', 'prix', 'garanties', 'juridiction'],
        'location': ['description_bien', 'loyer', 'depot_garantie', 'duree'],
        'terrain':  ['description_bien', 'prix', 'cadastre'],
    },
    'particulier_vendeur': {
        'vente':    ['description_bien', 'prix', 'conditions_financieres', 'penalites', 'garanties', 'juridiction'],
        'location': ['description_bien', 'loyer', 'depot_garantie', 'duree', 'conditions_resiliation', 'regles_maison'],
        'terrain':  ['description_bien', 'prix', 'cadastre', 'conditions_financieres'],
    },

    # ── Investisseur ──────────────────────────────────────────────────────────
    'investisseur': {
        'vente':    ['description_bien', 'prix', 'conditions_financieres', 'garanties', 'penalites'],
        'location': ['description_bien', 'loyer', 'depot_garantie', 'duree', 'conditions_financieres', 'penalites'],
        'terrain':  ['description_bien', 'prix', 'conditions_financieres', 'usage_terrain', 'cadastre'],
    },

    # ── Pros ──────────────────────────────────────────────────────────────────
    'agent':    {'location': ['ALL'], 'vente': ['ALL'], 'terrain': ['ALL']},
    'banquier': {
        'vente':    ['prix', 'conditions_financieres', 'hypotheque', 'echeancier', 'penalites'],
        'location': ['loyer', 'depot_garantie', 'echeancier', 'penalites'],
        'terrain':  ['prix', 'conditions_financieres', 'hypotheque', 'cadastre'],
    },
}

def get_permission_prompt(user_role, contract_type):
    labels = {
        'particulier_acheteur': 'Particulier — Acheteur/Locataire',
        'particulier_vendeur':  'Particulier — Vendeur/Bailleur',
        'investisseur':         'Investisseur',
        'agent':                'Agent Immobilier',
        'banquier':             'Banquier',
    }
    restrictions = {
        'particulier_acheteur': 'Lecture seule sur prix et clauses financières.',
        'particulier_vendeur':  'Peut définir prix et conditions. Ne peut pas modifier clauses légales obligatoires.',
        'investisseur':         'Peut modifier conditions financières. Ne peut pas accéder aux clauses bancaires.',
        'agent':                'Accès complet à toutes les clauses.',
        'banquier':             'Accès uniquement aux clauses financières et hypothèques.',
    }
    perms = USER_PERMISSIONS.get(user_role, {}).get(contract_type, [])
    label = labels.get(user_role, user_role)
    restr = restrictions.get(user_role, '')

    if not perms:
        return f'ROLE : {label}\nPERMISSIONS : Lecture seule pour {contract_type}.\nRESTRICTIONS : {restr}'
    if 'ALL' in perms:
        return f'ROLE : {label}\nPERMISSIONS : Accès complet.\nRESTRICTIONS : {restr}'
    return f'ROLE : {label}\nPERMISSIONS : {", ".join(perms)} uniquement.\nRESTRICTIONS : {restr}'

print('✅ Permissions chargées')
print()
for role in USER_PERMISSIONS:
    print(get_permission_prompt(role, 'vente'))
    print()
def detect_contract_type(listing):
    combined = ' '.join([str(v) for v in listing.values() if v]).lower()
    if any(k in combined for k in ['terrain','parcelle','lot','hectare','agricole','constructible']):
        return 'terrain'
    if any(k in combined for k in ['location','louer','a louer','bail','loyer']):
        return 'location'
    doc_type = nlp(' '.join([str(listing.get('titre','') or ''), str(listing.get('description','') or '')[:300]]))
    for token in doc_type:
        if token.lemma_.lower() in ('terrain','parcelle','lot','hectare'):  return 'terrain'
        if token.lemma_.lower() in ('location','bail','loyer','louer'):     return 'location'
    return 'vente'

def format_listing_for_prompt(listing):
    labels = {'id':'ID','titre':'Titre','prix':'Prix (DT)','adresse':'Adresse',
              'localisation':'Localisation','description':'Description',
              'pieces':'Pieces','surface':'Superficie (m2)','type':'Type'}
    return '\n'.join([f'- {labels.get(k,k)} : {str(v)[:200]}' for k,v in listing.items() if v and str(v).strip() not in ('','None')])

def get_contract_title(contract_type, listing):
    combined = ' '.join([str(v) for v in listing.values() if v]).lower()
    if contract_type == 'terrain':
        return 'CONTRAT DE BAIL DE TERRAIN' if any(k in combined for k in ['louer','location','bail']) else 'CONTRAT DE VENTE DE TERRAIN'
    return {'location': "CONTRAT DE BAIL À USAGE D'HABITATION", 'vente': 'PROMESSE SYNALLAGMATIQUE DE VENTE'}.get(contract_type, 'CONTRAT IMMOBILIER')

def build_advanced_prompt(listing, contract_type, vendeur_info=None):
    '''
    Prompt enrichi avec TOUS les modules NLP avancés :
    NER filtré POS + noun chunks scorés + obligations détectées +
    RAG sémantique FAISS + transformation lexicale légale
    '''
    entities        = extract_entities_advanced(listing)
    listing_info    = format_listing_for_prompt(listing)
    listing_text    = ' '.join([str(v) for v in listing.values() if v])

    # RAG sémantique (NLP 6) — requête = titre + type
    rag_query   = f"{listing.get('titre','')} {listing.get('localisation','')} {contract_type}"
    rag_context = build_rag_context(rag_query, contract_type, top_k=4)

    # Noun chunks scorés (NLP 4)
    doc_listing = nlp(listing_text[:1000])
    ranked_chunks = extract_ranked_noun_chunks(doc_listing, top_n=6)

    # Transformation lexicale (NLP 2)
    titre_transformed, _ = transform_to_legal_terms_advanced(listing.get('titre','') or '')

    nlp_section = f'''ANALYSE NLP AVANCÉE (spaCy fr_lg + TF-IDF + FAISS) :
- Lieux (NER+POS) : {', '.join(entities['lieux'][:4]) or 'non détecté'}
- Biens (PROPERTY) : {', '.join(entities['biens'][:3]) or 'non détecté'}
- Montants (NER) : {', '.join(entities['montants'][:3]) or 'non détecté'}
- Docs légaux : {', '.join(entities['docs_legaux'][:3]) or 'non détecté'}
- Syntagmes clés (TF-IDF) : {', '.join([c['text'] for c in ranked_chunks[:4]]) or 'aucun'}
- Verbes d'action : {', '.join(entities['verbes_cles'][:5]) or 'aucun'}
- Obligations détectées : {len(entities['obligations'])} clause(s)
- Titre transformé : {titre_transformed[:80]}'''

    vendeur_block = (
        f"VENDEUR : {vendeur_info['nom']} | CIN : {vendeur_info['cin']} | Adresse : {vendeur_info['adresse']}"
        if vendeur_info and vendeur_info.get('nom')
        else 'VENDEUR : [NOM] | CIN : [CIN] | Adresse : [ADRESSE]'
    )

    system_prompt = (
        "Tu es un juriste expert en droit immobilier tunisien travaillant pour KADASTRA.\n"
        "Tu génères des contrats COMPLETS, DÉTAILLÉS et légalement conformes au Code des Obligations et Contrats (COC) tunisien.\n"
        "OBLIGATIONS ABSOLUES :\n"
        "1. Identifier les DEUX parties avec NOM COMPLET, CIN, adresse.\n"
        "2. Décrire le bien avec superficie exacte, adresse complète, titre foncier.\n"
        "3. Stipuler le prix EN CHIFFRES ET EN LETTRES en dinars tunisiens.\n"
        "4. Inclure MINIMUM 5 clauses d'obligation (doit, est tenu, s'engage, est interdit).\n"
        "5. Citer MINIMUM 3 articles de loi (COC, Loi 77-40, Code foncier).\n"
        "6. Inclure clauses : garanties, résiliation, juridiction, enregistrement fiscal.\n"
        "7. Terminer par bloc signature avec date, lieu, noms des parties.\n\n"
        f"{rag_context}\n\n"
        "FORMAT : Articles numérotés (Article 1, Article 2...). Français juridique formel. Contrat COMPLET sans résumé ni abréviation."
    )
    user_message = (
        f'Génère le contrat COMPLET : "{get_contract_title(contract_type, listing)}"\n\n'
        f'ANNONCE :\n{listing_info}\n\n'
        f'{vendeur_block}\n\n'
        f'{nlp_section}\n\n'
        'STRUCTURE OBLIGATOIRE DU CONTRAT :\n'
        'Article 1 — Identification des parties (NOM, CIN, adresse complète)\n'
        'Article 2 — Désignation du bien (adresse, superficie, titre foncier)\n'
        'Article 3 — Prix et modalités de paiement (chiffres ET lettres, DT)\n'
        'Article 4 — Obligations du vendeur/bailleur (références COC)\n'
        'Article 5 — Obligations de l\'acquéreur/locataire (références COC)\n'
        'Article 6 — Garanties légales (éviction, vices cachés, Art. 641 COC)\n'
        'Article 7 — Conditions de résiliation et pénalités\n'
        'Article 8 — Enregistrement fiscal et frais (recette des finances)\n'
        'Article 9 — Juridiction compétente (Tribunal de Première Instance)\n'
        'Article 10 — Signatures, date et lieu\n\n'
        'Génère le contrat INTÉGRAL avec tous les articles ci-dessus, en citant les articles du COC et de la Loi 77-40 :'
    )
    return system_prompt, user_message, entities

def call_groq_model(model_id, system_prompt, user_message, max_new_tokens=3000, temperature=0.1):
    payload = {
        'model': model_id,
        'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_message}],
        'max_tokens': max_new_tokens, 'temperature': temperature, 'stream': False
    }
    t0       = time.time()
    response = requests.post(GROQ_BASE_URL, headers=GROQ_HEADERS, json=payload, timeout=120)
    gen_time = round(time.time() - t0, 2)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip(), gen_time
    raise Exception(f'Groq {response.status_code}: {response.text[:200]}')

def call_llm(system_prompt, user_message, platform='esprit', model_id=None, max_tokens=3000):
    if platform == 'esprit':
        model_id = model_id or ESPRIT_MODEL
        start = time.time()
        resp  = client_llm.chat.completions.create(
            model=model_id,
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_message}],
            max_tokens=max_tokens, temperature=0.1
        )
        elapsed  = round(time.time() - start, 2)
        contract = resp.choices[0].message.content
        tokens   = resp.usage.total_tokens
        return contract, elapsed, tokens
    elif platform == 'groq':
        model_id = model_id or 'llama-3.1-8b-instant'
        contract, elapsed = call_groq_model(model_id, system_prompt, user_message, max_new_tokens=max_tokens)
        return contract, elapsed, 0
    raise ValueError(f'Plateforme inconnue : {platform}')

def save_to_training_dataset(user_message, contract, contract_type, listing, model_label=''):
    entry = {
        'instruction': 'Tu es un juriste expert en droit immobilier tunisien.',
        'input': user_message, 'output': contract,
        'contract_type': contract_type, 'listing_id': listing.get('id',''),
        'prix': listing.get('prix',''), 'localisation': listing.get('localisation','') or listing.get('adresse',''),
        'model': model_label
    }
    with open(DATASET_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def generate_contract_advanced(listing, contract_type=None, vendeur_info=None,
                                platform='esprit', model_id=None,
                                save_dataset=True, post_correct=True):
    '''
    Génération avancée avec tous les modules NLP intégrés.
    NOUVEAU : post_correct=True applique la correction grammaticale sur le contrat généré.
    '''
    if contract_type is None:
        contract_type = detect_contract_type(listing)

    system_prompt, user_message, entities = build_advanced_prompt(listing, contract_type, vendeur_info)
    contract, elapsed, tokens = call_llm(system_prompt, user_message, platform, model_id)

    # NLP 5 : correction du contrat généré
    if post_correct:
        contract_corrected = post_correct_contract(contract)
    else:
        contract_corrected = contract

    # NLP 7 : validation NLP du contrat
    nlp_report = validate_contract_nlp(contract_corrected, contract_type)

    messages = [
        {'role': 'system',    'content': system_prompt},
        {'role': 'user',      'content': user_message},
        {'role': 'assistant', 'content': contract_corrected}
    ]
    if save_dataset:
        save_to_training_dataset(user_message, contract_corrected, contract_type, listing, model_id or ESPRIT_MODEL)

    return {
        'contract':        contract_corrected,
        'contract_raw':    contract,
        'messages':        messages,
        'contract_type':   contract_type,
        'generation_time': elapsed,
        'tokens_used':     tokens,
        'nlp_entities':    entities,
        'nlp_report':      nlp_report,
        'vendeur_info':    vendeur_info,
        'platform':        platform,
        'model_id':        model_id or ESPRIT_MODEL,
        'modifications':   0,
    }

# ── Génération avec les 3 modèles ────────────────────────────────────────────
print('=== Génération avancée (NLP 7/7) avec les 3 modèles ===\n')
sessions_init = {}
models_init = [
    ('Llama-3.1-70B (ESPRIT)', 'esprit', ESPRIT_MODEL),
    ('Llama-3-8B (Groq)',      'groq',   'llama-3.1-8b-instant'),
    ('Llama-3-70B (Groq)',     'groq',   'llama-3.3-70b-versatile'),
]
for label, platform, mid in models_init:
    print(f'  [{label}]...', end=' ', flush=True)
    try:
        sess = generate_contract_advanced(listing, platform=platform, model_id=mid, save_dataset=True)
        sessions_init[label] = sess
        rep = sess['nlp_report']
        print(f'✅ {sess["generation_time"]}s | CCR_NLP={rep["ccr_nlp"]}% | Obligations={len(rep["obligations_found"])} | Refs={len(rep["legal_refs_found"])}')
    except Exception as e:
        print(f'❌ {e}')

contract_session = sessions_init.get('Llama-3.1-70B (ESPRIT)', next(iter(sessions_init.values()), None))
if contract_session:
    rep = contract_session['nlp_report']
    print(f'\n=== Rapport NLP du meilleur contrat ===')
    print(f'  CCR NLP     : {rep["ccr_nlp"]}%  ({rep["score_nlp"]}/{rep["max_score_nlp"]})')
    print(f'  Parties NER : {rep["parties_check"]["parties_found"]}')
    print(f'  Obligations : {len(rep["obligations_found"])}')
    print(f'  Refs légales: {rep["legal_refs_found"][:3]}')
    if rep['issues']:
        print(f'  Issues      : {rep["issues"][:3]}')

import ipywidgets as widgets
from IPython.display import display

def build_chat_ui(contract_session, user_role='particulier_acheteur'):
    contract_type = contract_session['contract_type']
    platform      = contract_session.get('platform', 'esprit')
    model_id      = contract_session.get('model_id', ESPRIT_MODEL)
    perms    = USER_PERMISSIONS.get(user_role, {}).get(contract_type, [])
    perm_str = 'TOUTES' if 'ALL' in perms else (', '.join(perms) if perms else 'LECTURE SEULE')
    rep      = contract_session.get('nlp_report', {})

    system_prompt = (
        f'Tu es un assistant juridique immobilier tunisien expert.\n'
        f'{get_permission_prompt(user_role, contract_type)}\n\n'
        f'Contrat :\n{contract_session["contract"]}'
    )
    history = []

    header = widgets.HTML(
        f'<b>KADASTRA CHAT</b> | {contract_type.upper()} | {user_role.upper()} | '
        f'CCR_NLP={rep.get("ccr_nlp","?")}% | {platform.upper()}'
        f'<br><small>Permissions : {perm_str}</small><hr>'
    )
    chat_out   = widgets.Output(layout=widgets.Layout(border='1px solid #ddd', min_height='150px', max_height='350px', overflow_y='auto', padding='8px'))
    text_input = widgets.Text(placeholder='Votre question…', layout=widgets.Layout(width='75%'))
    send_btn   = widgets.Button(description='Envoyer', button_style='primary')
    clear_btn  = widgets.Button(description='Effacer', button_style='warning')

    # ── Dropdown pour changer de rôle dynamiquement ───────────────────────────
    role_dropdown = widgets.Dropdown(
        options=[
            ('Particulier — Acheteur',  'particulier_acheteur'),
            ('Particulier — Vendeur',   'particulier_vendeur'),
            ('Investisseur',            'investisseur'),
            ('Agent Immobilier',        'agent'),
            ('Banquier',                'banquier'),
        ],
        value=user_role,
        description='Rôle :',
        layout=widgets.Layout(width='250px')
    )

    def on_role_change(change):
        new_role     = change['new']
        new_perms    = USER_PERMISSIONS.get(new_role, {}).get(contract_type, [])
        new_perm_str = 'TOUTES' if 'ALL' in new_perms else (', '.join(new_perms) if new_perms else 'LECTURE SEULE')
        header.value = (
            f'<b>KADASTRA CHAT</b> | {contract_type.upper()} | {new_role.upper()} | '
            f'CCR_NLP={rep.get("ccr_nlp","?")}% | {platform.upper()}'
            f'<br><small>Permissions : {new_perm_str}</small><hr>'
        )
        # Mettre à jour le system_prompt avec le nouveau rôle
        nonlocal system_prompt
        system_prompt = (
            f'Tu es un assistant juridique immobilier tunisien expert.\n'
            f'{get_permission_prompt(new_role, contract_type)}\n\n'
            f'Contrat :\n{contract_session["contract"]}'
        )
        history.clear()
        chat_out.clear_output()
        with chat_out:
            print(f'🔄 Rôle changé → {new_role} | Permissions : {new_perm_str}')

    role_dropdown.observe(on_role_change, names='value')

    def on_send(_):
        q = text_input.value.strip()
        if not q: return
        text_input.value = ''
        history.append({'role': 'user', 'content': q})
        with chat_out:
            print(f'👤 {q}')
        try:
            ans, _, _ = call_llm(system_prompt, q, platform, model_id, max_tokens=500)
            history.append({'role': 'assistant', 'content': ans})
            with chat_out:
                print(f'🤖 {ans}\n')
        except Exception as e:
            with chat_out:
                print(f'❌ {e}\n')

    def on_clear(_):
        history.clear()
        chat_out.clear_output()

    send_btn.on_click(on_send)
    clear_btn.on_click(on_clear)
    text_input.on_submit(on_send)

    display(widgets.VBox([
        header,
        role_dropdown,
        chat_out,
        widgets.HBox([text_input, send_btn, clear_btn])
    ]))
    return history

if contract_session:
    chat_history = build_chat_ui(contract_session, user_role='particulier_acheteur')
else:
    print("⚠️  Générer un contrat d'abord (cellule 4C).")
def evaluate_contract_quality(contract_text, contract_type='vente'):
    '''KPI combiné : keyword match + score NLP.'''
    c = contract_text.lower()
    clauses = {
        'vente':   {'Identification':['vendeur','acheteur','cin','acquereur','acquéreur','désignation','nom complet'],
                    'Description':   ['superficie','adresse','localisation','bien','immeuble','appartement','villa','désignation'],
                    'Prix':          ['prix','dinars','contrepartie','dt','paiement','virement','chèque','lettres'],
                    'Transfert':     ['propriete','propriété','cles','clés','remise','transfert','jouissance','possession'],
                    'Garanties':     ['garantie','vice','eviction','éviction','décennale','caché','art. 641','art.641'],
                    'Frais':         ['frais','enregistrement','honoraires','3%','fiscale','recette','droits'],
                    'Juridiction':   ['tribunal','juridiction','compétent','première instance','litige'],
                    'Obligations':   ['doit','est tenu','s engage','interdit','obligation','article'],
                    'Resiliation':   ['résiliation','résoudre','annulation','pénalité','penalite'],
                    'Signatures':    ['signature','signé','seing','lu et approuvé','fait à']},
        'location':{'Identification':['bailleur','locataire','cin','preneur','désignation','nom'],
                    'Description':   ['superficie','adresse','bien loué','logement','appartement','local'],
                    'Duree':         ['durée','duree','debut','début','fin','mois','an','terme','période'],
                    'Loyer':         ['loyer','dinars','redevance','dt','mensuel','paiement','10 du mois'],
                    'Depot':         ['garantie','dépôt','depot','caution','mois de loyer','restitution'],
                    'Obligations':   ['obligation','interdit','usage','sous-location','entretien','état'],
                    'Resiliation':   ['résiliation','resiliation','préavis','preavis','tribunal','congé'],
                    'Refs_legales':  ['loi 77-40','loi77-40','art.','article','coc','code'],
                    'Signatures':    ['signature','signé','seing','lu et approuvé','fait à']},
        'terrain': {'Identification':['vendeur','acheteur','cin','acquéreur','acquereur','désignation'],
                    'Description':   ['terrain','superficie','parcelle','hectare','m²','délimitation'],
                    'Cadastre':      ['titre foncier','cadastr','foncier','immatriculé','registre','numéro'],
                    'Nature':        ['agricole','constructible','nature','usage','urbanistique','statut'],
                    'Prix':          ['prix','dinars','contrepartie','dt','paiement','lettres'],
                    'Hypotheques':   ['hypothèque','hypotheque','libre','saisie','réel','charge'],
                    'Garanties':     ['garantie','éviction','eviction','vice','caché','art.'],
                    'Juridiction':   ['tribunal','juridiction','compétent','litige','première instance'],
                    'Obligations':   ['doit','est tenu','s engage','interdit','obligation'],
                    'Signatures':    ['signature','signé','seing','lu et approuvé','fait à']},
    }
    selected = clauses.get(contract_type, clauses['vente'])
    kw_results = {n: any(k in c for k in kws) for n, kws in selected.items()}
    kw_score   = sum(kw_results.values())
    kw_total   = len(kw_results)

    # Score NLP (NLP 7)
    nlp_rep = validate_contract_nlp(contract_text, contract_type)

    combined_ccr = round((kw_score / kw_total * 0.6 + nlp_rep['ccr_nlp'] / 100 * 0.4) * 100, 1)

    return {
        'clean_contract_rate': combined_ccr,
        'kw_ccr':              round(kw_score / kw_total * 100, 1),
        'nlp_ccr':             nlp_rep['ccr_nlp'],
        'error_rate':          round(100 - combined_ccr, 1),
        'clauses_found':       kw_score,
        'clauses_total':       kw_total,
        'missing_clauses':     [n for n, f in kw_results.items() if not f],
        'nlp_obligations':     len(nlp_rep['obligations_found']),
        'nlp_legal_refs':      len(nlp_rep['legal_refs_found']),
        'is_clean':            combined_ccr >= 80,
    }

print('=== KPIs avancés (keyword + NLP) ===')
for label, sess in sessions_init.items():
    ev = evaluate_contract_quality(sess['contract'], sess['contract_type'])
    status = '✅ OK' if ev['clean_contract_rate'] >= 80 else '⚠️'
    print(f'  [{label}]')
    print(f'    CCR combiné={ev["clean_contract_rate"]}% [{status}] | KW={ev["kw_ccr"]}% | NLP={ev["nlp_ccr"]}%')
    print(f'    Obligations={ev["nlp_obligations"]} | Refs légales={ev["nlp_legal_refs"]} | Temps={sess["generation_time"]}s')

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import unicodedata

def clean_text_for_pdf(text):
    for old, new in [('—','-'), ('\u2019',"'"), ('\u201c','"'), ('\u201d','"'), ('•','-')]:
        text = text.replace(old, new)
    text = unicodedata.normalize('NFKD', text)
    return re.sub(r'[^\x20-\x7E\t\n\xC0-\xFF]', '', text)  # ← regex sur une seule ligne

def safe_text(text, max_len=95):
    result = []
    for line in text.split('\n'):
        while len(line) > max_len:
            result.append(line[:max_len]); line = line[max_len:]
        result.append(line)
    return '\n'.join(result)

def generate_pdf_contract(contract_text, listing, contract_type, model_label='LLM',
                           nlp_report=None, n_modifications=0, output_path=None):
    os.makedirs('/content/contracts', exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20); pdf.set_text_color(0, 120, 100)
    pdf.cell(0, 10, 'KADASTRA', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 10); pdf.set_text_color(100, 100, 100)
    ccr_nlp = nlp_report.get('ccr_nlp', '?') if nlp_report else '?'
    pdf.cell(0, 6, f'Modèle : {model_label} | CCR_NLP={ccr_nlp}% | NLP 7/7',
             align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(0, 120, 100)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2); pdf.ln(6)
    pdf.set_font('Helvetica', 'B', 13); pdf.set_text_color(0, 0, 0)
    titles = {'vente':'PROMESSE SYNALLAGMATIQUE DE VENTE','location':"BAIL À USAGE D'HABITATION",'terrain':'VENTE / BAIL DE TERRAIN'}
    pdf.cell(0, 9, f'CONTRAT : {titles.get(contract_type,"IMMOBILIER")}', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font('Helvetica', '', 10)
    for line in safe_text(clean_text_for_pdf(contract_text)).split('\n'):
        if not line.strip(): pdf.ln(3); continue
        if line.strip().upper() == line.strip() and len(line.strip()) > 5:
            pdf.set_font('Helvetica', 'B', 10); pdf.set_text_color(0, 80, 60)
            pdf.multi_cell(0, 6, line.strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font('Helvetica', '', 10); pdf.set_text_color(0, 0, 0)
        else:
            pdf.multi_cell(0, 5, line.strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if output_path is None:
        output_path = f"/content/contracts/contrat_{contract_type}_{listing.get('id','x')}.pdf"
    pdf.output(output_path)
    return output_path

os.makedirs('/content/contracts', exist_ok=True)
for label, sess in sessions_init.items():
    safe_label = label.replace(' ','_').replace('(','').replace(')','')
    path = f"/content/contracts/contrat_{sess['contract_type']}_{safe_label}.pdf"
    pdf_path = generate_pdf_contract(
        sess['contract'], listing, sess['contract_type'],
        model_label=label, nlp_report=sess.get('nlp_report'),
        output_path=path
    )
    print(f'PDF : {pdf_path}')
    try:
        from google.colab import files; files.download(pdf_path)
    except Exception:
        pass
import time

def fetch_listing_safe(contract_type=None, max_retries=3, wait=5):
    '''fetch_listing avec retry automatique si la DB est temporairement inaccessible.'''
    for attempt in range(1, max_retries + 1):
        try:
            lst = fetch_listing(contract_type=contract_type)
            return lst
        except Exception as e:
            print(f'  ⚠️  DB tentative {attempt}/{max_retries} : {e}')
            if attempt < max_retries:
                print(f'  ⏳ Attente {wait}s avant retry...')
                time.sleep(wait)
    print(f'  ❌ DB inaccessible après {max_retries} tentatives.')
    return None

def probe_groq_model(model_id):
    try:
        text, _ = call_groq_model(model_id, 'Tu es un assistant.', 'Dis juste OK.', max_new_tokens=10)
        return len(text) > 0
    except Exception:
        return False

GROQ_MODELS_OK = {}
for label, model_id in GROQ_MODELS.items():
    print(f'  {label:20s} → ', end='')
    if probe_groq_model(model_id):
        GROQ_MODELS_OK[label] = model_id; print('✅')
    else:
        print('❌')

MODELS_TO_COMPARE = {'Llama-3.1-70B (ESPRIT)': ('esprit', ESPRIT_MODEL)}
for label, mid in GROQ_MODELS_OK.items():
    MODELS_TO_COMPARE[f'{label} (Groq)'] = ('groq', mid)

def compare_models_on_listing(listing, contract_type):
    comparison = {}
    for model_label, (platform, model_id) in MODELS_TO_COMPARE.items():
        try:
            sess = generate_contract_advanced(listing, contract_type, platform=platform, model_id=model_id, save_dataset=False)
            ev   = evaluate_contract_quality(sess['contract'], contract_type)
            comparison[model_label] = {
                'platform':    platform,
                'model_id':    model_id,
                'mean_ccr':    ev['clean_contract_rate'],
                'kw_ccr':      ev['kw_ccr'],
                'nlp_ccr':     ev['nlp_ccr'],
                'error_rate':  ev['error_rate'],
                'mean_time':   sess['generation_time'],
                'obligations': ev['nlp_obligations'],
                'legal_refs':  ev['nlp_legal_refs'],
            }
        except Exception as e:
            print(f'  [ERREUR] {model_label}: {e}')
    return comparison

CONTRACT_TYPES = ['vente', 'location', 'terrain']
all_results    = {label: {} for label in MODELS_TO_COMPARE}

for ctype in CONTRACT_TYPES:
    print(f'\n=== {ctype.upper()} ===')
    lst = fetch_listing_safe(contract_type=ctype)  # ← retry automatique
    if not lst:
        print(f'  ⏭️  {ctype} ignoré — DB inaccessible')
        continue
    comp = compare_models_on_listing(lst, ctype)
    for model_label, m in comp.items():
        all_results[model_label][ctype] = m
        print(f'  {model_label:35s} | CCR={m["mean_ccr"]:5.1f}% (KW={m["kw_ccr"]}% NLP={m["nlp_ccr"]}%) | Ob={m["obligations"]} Ref={m["legal_refs"]} | {m["mean_time"]}s')
# ── Tableau final + verdict + sauvegarde ─────────────────────────────────────
print('\n' + '='*90)
print('TABLEAU COMPARATIF FINAL — NLP 7/7')
print('='*90)

model_scores = {}; model_avg_ccr = {}; model_avg_time = {}
max_pts = len(CONTRACT_TYPES) * 7  # 7 critères par type

for model_label, (platform, _) in MODELS_TO_COMPARE.items():
    total_pts, ccr_list, time_list = 0, [], []
    for ctype in CONTRACT_TYPES:
        m = all_results[model_label].get(ctype)
        if not m: continue
        pts = (3 if m['mean_ccr']   >= 80 else 0) +               (2 if m['error_rate']  <  10 else 0) +               (1 if m['mean_time']   <  10 else 0) +               (1 if m['obligations'] >=  3 else 0)
        total_pts += pts; ccr_list.append(m['mean_ccr']); time_list.append(m['mean_time'])
        print(f'  {model_label:35s} | {ctype:10s} | CCR={m["mean_ccr"]:5.1f}% | NLP={m["nlp_ccr"]}% | Ob={m["obligations"]} | {m["mean_time"]}s | {pts}/7')
    model_scores[model_label]   = total_pts
    model_avg_ccr[model_label]  = round(sum(ccr_list)/len(ccr_list),  1) if ccr_list  else 0
    model_avg_time[model_label] = round(sum(time_list)/len(time_list), 2) if time_list else 0
    print('-'*90)

best = max(model_scores, key=model_scores.get)
best_platform, best_model_id = MODELS_TO_COMPARE[best]

print(f'\n✅ MEILLEUR MODÈLE : {best}')
print(f'   Score   : {model_scores[best]}/{max_pts} | CCR moyen : {model_avg_ccr[best]}% | Temps : {model_avg_time[best]}s')

best_meta = {
    'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    'best_model_label': best, 'platform': best_platform, 'model_id': best_model_id,
    'score': model_scores[best], 'max_score': max_pts,
    'mean_ccr': model_avg_ccr[best], 'mean_time_s': model_avg_time[best],
    'nlp_version': 'advanced_7_7',
    'nlp_modules': ['NER+domain','lemma+fuzzy','POS_used','chunks_tfidf','post_correct','faiss_rag','contract_nlp_val'],
    'faiss_index': FAISS_INDEX_PATH,
}
json.dump(best_meta, open(BEST_LLM_META_PATH, 'w'), ensure_ascii=False, indent=2)
print(f'\n✅ Métadonnées sauvegardées : {BEST_LLM_META_PATH}')
try:
    from google.colab import files; files.download(BEST_LLM_META_PATH)
except Exception:
    pass

# API Django — version NLP avancée
#
# @require_POST
# def generate_contract(request):
#     data          = json.loads(request.body)
#     listing       = fetch_listing(data.get('listing_id'))
#     contract_type = detect_contract_type(listing)
#
#     # Charger FAISS au démarrage du serveur (pas à chaque requête)
#     # faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#
#     with open(BEST_LLM_META_PATH) as f:
#         best_meta = json.load(f)
#
#     session = generate_contract_advanced(
#         listing, contract_type,
#         vendeur_info=data.get('vendeur_info'),
#         platform=best_meta['platform'],
#         model_id=best_meta['model_id'],
#         post_correct=True,     # NLP 5
#     )
#     nlp_rep = session['nlp_report']
#
#     return JsonResponse({
#         'contract':       session['contract'],
#         'type':           contract_type,
#         'ccr_combined':   evaluate_contract_quality(session['contract'], contract_type)['clean_contract_rate'],
#         'ccr_nlp':        nlp_rep['ccr_nlp'],
#         'obligations':    len(nlp_rep['obligations_found']),
#         'legal_refs':     nlp_rep['legal_refs_found'],
#         'issues':         nlp_rep['issues'],
#         'nlp_entities':   nlp_rep['nlp_entities'],
#     })

print('Phase 6 — API Django NLP avancée (7/7 modules intégrés)')
