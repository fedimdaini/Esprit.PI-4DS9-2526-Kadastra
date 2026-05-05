"""
NLP Config — Constants, dictionaries, legal chunks for Tunisian real estate.
Extracted from the Colab notebook (Score NLP 7/7).
"""

# ── Tunisian Locations (GPE/LOC for EntityRuler) ──────────────────────────────
TUNISIAN_LOCATIONS = [
    'Tunis', 'Sfax', 'Sousse', 'Kairouan', 'Bizerte', 'Gabès',
    'Ariana', 'Gafsa', 'Monastir', 'Ben Arous', 'Kasserine', 'Médenine',
    'Nabeul', 'Tataouine', 'Béja', 'Jendouba', 'Mahdia', 'Sidi Bouzid',
    'Siliana', 'Kébili', 'Le Kef', 'Tozeur', 'Manouba', 'Zaghouan',
    'La Marsa', 'Carthage', 'Sidi Bou Saïd', 'Hammamet',
    'Djerba', 'Zarzis', 'Tabarka', 'Ain Draham', 'El Aouina',
]

# ── Property Types (PROPERTY entity) ─────────────────────────────────────────
RE_PROPERTY_TYPES = [
    'villa', 'appartement', 'maison', 'duplex', 'studio', 'S+1', 'S+2',
    'S+3', 'S+4', 'S+5', 'bungalow', 'ferme', 'local commercial',
    'bureau', 'entrepôt', 'hangar', 'titre foncier', 'terrain agricole',
    'terrain constructible', 'lot de terrain', 'parcelle',
]

# ── Legal Documents (LEGAL_DOC entity) ────────────────────────────────────────
LEGAL_DOCS = [
    'titre foncier', 'COC', 'code des obligations', 'loi 77-40',
    'loi 90-17', 'code civil tunisien', 'registre foncier',
    'attestation de propriété', 'acte de vente', 'promesse de vente',
    'contrat de bail', 'compromis de vente',
]

# ── Legal Dictionary (NLP 2 — lexical transformation) ────────────────────────
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
    'titre foncier': 'titre de propriété foncière immatriculé',
    'moudawana': 'code du statut personnel',
    'recette des finances': 'bureau de perception fiscale',
    'immatriculer': 'inscrire au registre foncier',
    'cadastre': 'service du cadastre et des finances',
}

# ── Obligation Patterns (NLP 3 — POS + obligations) ──────────────────────────
OBLIGATION_PATTERNS = {
    'obligation_positive': ['doit', 'devra', 'est tenu', 'est obligé', "s'engage", "s'oblige"],
    'obligation_negative': ['ne doit pas', 'est interdit', 'ne peut pas', 'est défendu', 'ne saurait'],
    'permission':          ['peut', 'pourra', 'est autorisé', 'a le droit', 'est en droit'],
    'condition':           ['si', 'en cas de', 'sous réserve', 'à condition', 'sauf si'],
}

# ── Legal Reference Corpus (NLP 4 — TF-IDF) ─────────────────────────────────
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

# ── Legal Nouns for chunk scoring ─────────────────────────────────────────────
LEGAL_NOUNS = {
    'maison', 'villa', 'appartement', 'terrain', 'lot', 'parcelle',
    'superficie', 'surface', 'chambre', 'pièce', 'étage', 'garage',
    'jardin', 'piscine', 'prix', 'loyer', 'caution', 'charge',
    'syndic', 'copropriété', 'titre', 'foncier', 'cadastre',
    'bien', 'propriété', 'immeuble', 'logement', 'résidence',
}

# ── Grammar Fixes (NLP 5 — regex corrections, no Java needed) ────────────────
GRAMMAR_FIXES_FR = [
    (r'(?i)du moi',      'du mois'),
    (r'(?i)au moi',      'au mois'),
    (r'(?i)chaque moi',  'chaque mois'),
    (r'(?i)par moi',     'par mois'),
    (r'(?i)loier',       'loyer'),
    (r'(?i)causion',     'caution'),
    (r'(?i)addresse',    'adresse'),
    (r'(?i)resiliation', 'résiliation'),
    (r'(?i)bailleure?',  'bailleur'),
    (r'(?i)acquereur',   'acquéreur'),
    (r'(?i)propiétaire', 'propriétaire'),
    (r'(?i)vendreur',    'vendeur'),
]

# ── Legal Chunks for FAISS RAG (NLP 6) ───────────────────────────────────────
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

# ── Clause checks for validation (NLP 7) ─────────────────────────────────────
CLAUSE_CHECKS = {
    'vente': {
        'Identification': ['vendeur', 'acheteur', 'cin', 'acquereur', 'acquéreur', 'désignation', 'nom complet'],
        'Description':    ['superficie', 'm²', 'adresse', 'bien', 'immeuble', 'appartement', 'villa', 'désignation'],
        'Prix':           ['prix', 'dinars', 'contrepartie', 'dt', 'paiement', 'virement', 'chèque', 'lettres'],
        'Transfert':      ['propriete', 'propriété', 'cles', 'clés', 'remise', 'transfert', 'jouissance', 'possession'],
        'Garanties':      ['garantie', 'vice', 'eviction', 'éviction', 'décennale', 'caché', 'art. 641', 'art.641'],
        'Frais':          ['frais', 'enregistrement', 'honoraires', '3%', 'fiscale', 'recette', 'droits'],
        'Juridiction':    ['tribunal', 'juridiction', 'compétent', 'première instance', 'litige'],
        'Obligations':    ['doit', 'est tenu', 's engage', 'interdit', 'obligation', 'article'],
        'Resiliation':    ['résiliation', 'résoudre', 'annulation', 'pénalité', 'penalite'],
        'Signatures':     ['signature', 'signé', 'seing', 'lu et approuvé', 'fait à'],
    },
    'location': {
        'Identification': ['bailleur', 'locataire', 'cin', 'preneur', 'désignation', 'nom'],
        'Description':    ['superficie', 'adresse', 'bien loué', 'logement', 'appartement', 'local'],
        'Duree':          ['durée', 'duree', 'debut', 'début', 'fin', 'mois', 'an', 'terme', 'période'],
        'Loyer':          ['loyer', 'dinars', 'redevance', 'dt', 'mensuel', 'paiement', '10 du mois'],
        'Depot':          ['garantie', 'dépôt', 'depot', 'caution', 'mois de loyer', 'restitution'],
        'Obligations':    ['obligation', 'interdit', 'usage', 'sous-location', 'entretien', 'état'],
        'Resiliation':    ['résiliation', 'resiliation', 'préavis', 'preavis', 'tribunal', 'congé'],
        'Refs_legales':   ['loi 77-40', 'loi77-40', 'art.', 'article', 'coc', 'code'],
        'Signatures':     ['signature', 'signé', 'seing', 'lu et approuvé', 'fait à'],
    },
    'terrain': {
        'Identification': ['vendeur', 'acheteur', 'cin', 'acquéreur', 'acquereur', 'désignation'],
        'Description':    ['terrain', 'superficie', 'parcelle', 'hectare', 'm²', 'délimitation'],
        'Cadastre':       ['titre foncier', 'cadastr', 'foncier', 'immatriculé', 'registre', 'numéro'],
        'Nature':         ['agricole', 'constructible', 'nature', 'usage', 'urbanistique', 'statut'],
        'Prix':           ['prix', 'dinars', 'contrepartie', 'dt', 'paiement', 'lettres'],
        'Hypotheques':    ['hypothèque', 'hypotheque', 'libre', 'saisie', 'réel', 'charge'],
        'Garanties':      ['garantie', 'éviction', 'eviction', 'vice', 'caché', 'art.'],
        'Juridiction':    ['tribunal', 'juridiction', 'compétent', 'litige', 'première instance'],
        'Obligations':    ['doit', 'est tenu', 's engage', 'interdit', 'obligation'],
        'Signatures':     ['signature', 'signé', 'seing', 'lu et approuvé', 'fait à'],
    },
}

# ── User Permissions by Role ─────────────────────────────────────────────────
USER_PERMISSIONS = {
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
    'investisseur': {
        'vente':    ['description_bien', 'prix', 'conditions_financieres', 'garanties', 'penalites'],
        'location': ['description_bien', 'loyer', 'depot_garantie', 'duree', 'conditions_financieres', 'penalites'],
        'terrain':  ['description_bien', 'prix', 'conditions_financieres', 'usage_terrain', 'cadastre'],
    },
    'agent':    {'location': ['ALL'], 'vente': ['ALL'], 'terrain': ['ALL']},
    'banquier': {
        'vente':    ['prix', 'conditions_financieres', 'hypotheque', 'echeancier', 'penalites'],
        'location': ['loyer', 'depot_garantie', 'echeancier', 'penalites'],
        'terrain':  ['prix', 'conditions_financieres', 'hypotheque', 'cadastre'],
    },
}
