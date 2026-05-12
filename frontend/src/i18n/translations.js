/**
 * translations.js — Kadastra bilingual string table
 * Supports: 'fr' (French, default) and 'en' (English)
 * Contract generation always stays in French — not translated here.
 */

const translations = {

  // ── General / App shell ────────────────────────────────────────────────────
  app: {
    loading:    { fr: 'Chargement...', en: 'Loading...' },
    error:      { fr: 'Erreur',        en: 'Error' },
    retry:      { fr: 'Réessayer',     en: 'Retry' },
    confirm:    { fr: 'Confirmer',     en: 'Confirm' },
    cancel:     { fr: 'Annuler',       en: 'Cancel' },
    close:      { fr: 'Fermer',        en: 'Close' },
    save:       { fr: 'Enregistrer',   en: 'Save' },
    search:     { fr: 'Rechercher...', en: 'Search...' },
    // Listings page
    exploreTitle:       { fr: 'Exploration Immobilière',  en: 'Property Explorer'   },
    exploreSubtotal:    { fr: 'Découvrez les {n} meilleures opportunités en Tunisie', en: 'Discover {n} top opportunities in Tunisia' },
    exploreSearching:   { fr: 'Recherche des meilleures opportunités...', en: 'Searching for the best opportunities...' },
    sortNewest:         { fr: 'Plus récentes',            en: 'Newest first'        },
    sortPriceAsc:       { fr: 'Prix croissant',           en: 'Price: low to high'  },
    sortPriceDesc:      { fr: 'Prix décroissant',         en: 'Price: high to low'  },
    sortSurface:        { fr: 'Plus grande surface',      en: 'Largest area'        },
    noResults:          { fr: 'Aucun résultat',           en: 'No results'          },
    noResultsDesc:      { fr: "Essayez d'élargir vos critères de recherche ou de réinitialiser les filtres.", en: 'Try widening your search criteria or resetting the filters.' },
    reset:              { fr: 'Réinitialiser',            en: 'Reset'               },
    connectionError:    { fr: 'Erreur de connexion',      en: 'Connection error'    },
    connectionErrorDesc:{ fr: 'Impossible de joindre le serveur. Assurez-vous que le backend Django est actif sur le port 8000.', en: 'Cannot reach the server. Make sure the Django backend is running on port 8000.' },
    footerCopy:         { fr: 'Plateforme immobilière avancée. Tous droits réservés.', en: 'Advanced real estate platform. All rights reserved.' },
  },

  // ── Navbar ─────────────────────────────────────────────────────────────────
  nav: {
    listings:  { fr: 'Annonces',  en: 'Listings'  },
    dashboard: { fr: 'Stats',     en: 'Stats'     },
    contracts: { fr: 'Contrats',  en: 'Contracts' },
    map:       { fr: 'Carte',     en: 'Map'       },
    logout:    { fr: 'Déconnexion', en: 'Logout'  },
    search:    { fr: 'Rechercher...', en: 'Search...' },
  },

  // ── Auth (login / register) ────────────────────────────────────────────────
  auth: {
    signIn:               { fr: 'Connectez-vous à votre compte', en: 'Sign in to your account' },
    signUp:               { fr: 'Créez votre compte',            en: 'Create your account' },
    noAccount:            { fr: "Pas encore de compte ?",        en: "Don't have an account?" },
    alreadyAccount:       { fr: 'Déjà un compte ?',              en: 'Already have an account?' },
    registerLink:         { fr: "S'inscrire",                    en: 'Sign up' },
    loginLink:            { fr: 'Se connecter',                  en: 'Sign in' },
    loginBtn:             { fr: 'Se connecter',                  en: 'Sign in' },
    registerBtn:          { fr: "S'inscrire",                    en: 'Sign up' },
    username:             { fr: "Nom d'utilisateur",             en: 'Username' },
    password:             { fr: 'Mot de passe',                  en: 'Password' },
    confirmPassword:      { fr: 'Confirmer mot de passe',        en: 'Confirm password' },
    email:                { fr: 'Email',                         en: 'Email' },
    firstName:            { fr: 'Prénom',                        en: 'First name' },
    lastName:             { fr: 'Nom',                           en: 'Last name' },
    accountType:          { fr: 'Type de compte',                en: 'Account type' },
    agencyName:           { fr: "Nom de l'agence",               en: 'Agency name' },
    licenseNumber:        { fr: 'Numéro de licence',             en: 'License number' },
    bankName:             { fr: 'Nom de la banque',              en: 'Bank name' },
    branch:               { fr: 'Agence',                        en: 'Branch' },
    passwordMismatch:     { fr: 'Les mots de passe ne correspondent pas', en: 'Passwords do not match' },
    // User type options
    typeParticulier:      { fr: '👤 Particulier',                en: '👤 Individual'     },
    typePartDesc:         { fr: 'Acheter ou vendre un bien',     en: 'Buy or sell property' },
    typeInvestisseur:     { fr: '💼 Investisseur',               en: '💼 Investor'       },
    typeInvestDesc:       { fr: "Investir dans l'immobilier",    en: 'Invest in real estate' },
    typeAgent:            { fr: '🏢 Agent immobilier',           en: '🏢 Real estate agent' },
    typeAgentDesc:        { fr: 'Gérer des annonces',            en: 'Manage listings'   },
    typeBanquier:         { fr: '🏦 Banquier',                   en: '🏦 Banker'         },
    typeBanquierDesc:     { fr: 'Financer des transactions',     en: 'Finance transactions' },
  },

  // ── Dashboard ──────────────────────────────────────────────────────────────
  dashboard: {
    // Particulier
    titleParticulier:    { fr: 'Tableau de Bord Sécurisé',          en: 'Secure Dashboard'           },
    subtitleParticulier: { fr: 'Surveillez vos recherches et analysez les risques locaux en temps réel.', en: 'Monitor your searches and analyze local risks in real time.' },
    marketCard:          { fr: 'Marché Actuel',                     en: 'Current Market'             },
    marketSub:           { fr: 'Annonces analysées ce mois',        en: 'Listings analyzed this month' },
    safeZones:           { fr: 'Zones Sûres',                       en: 'Safe Zones'                 },
    safeZonesSub:        { fr: 'Indice de sécurité moyen Tunisie',  en: 'Average security index Tunisia' },
    avgPrice:            { fr: 'Prix Moyen',                        en: 'Avg. Price'                 },
    avgPriceSub:         { fr: 'Basé sur vos critères',             en: 'Based on your criteria'     },
    // Investisseur
    titleInvestisseur:    { fr: "Intelligence d'Investissement",      en: 'Investment Intelligence'    },
    subtitleInvestisseur: { fr: 'Analyse prédictive et détection d\'opportunités à haut rendement.', en: 'Predictive analysis and high-yield opportunity detection.' },
    opportunities:       { fr: 'Opportunités',                      en: 'Opportunities'              },
    opportunitiesSub:    { fr: 'Biens sous-évalués détectés',        en: 'Undervalued properties detected' },
    coverage:            { fr: 'Couverture',                        en: 'Coverage'                   },
    coverageSub:         { fr: 'Annonces filtrées par IA',          en: 'AI-filtered listings'       },
    luxury:              { fr: 'Haut Standing',                     en: 'Luxury'                     },
    luxurySub:           { fr: 'Patrimoine de luxe disponible',     en: 'Luxury properties available' },
    // Agent
    titleAgent:          { fr: 'Console de Gestion Agent',          en: 'Agent Management Console'   },
    subtitleAgent:       { fr: 'Gérez vos mandats et suivez la performance de votre portefeuille.', en: 'Manage your mandates and track your portfolio performance.' },
    mandats:             { fr: 'Mandats Actifs',                    en: 'Active Mandates'            },
    mandatsSub:          { fr: 'Propriétés sous votre gestion',     en: 'Properties under management' },
    clients:             { fr: 'Base Clients',                      en: 'Client Base'                },
    clientsSub:          { fr: 'Acquéreurs potentiels qualifiés',   en: 'Qualified potential buyers'  },
    performance:         { fr: 'Performance',                       en: 'Performance'                },
    performanceSub:      { fr: 'Taux de conversion moyen',          en: 'Average conversion rate'    },
    // Banquier
    titleBanquier:       { fr: 'Analyse de Risque Crédit',          en: 'Credit Risk Analysis'       },
    subtitleBanquier:    { fr: 'Validation des dossiers et évaluation des garanties immobilières.', en: 'File validation and real estate collateral assessment.' },
    dossiers:            { fr: 'Dossiers',                          en: 'Files'                      },
    dossiersSub:         { fr: "Demandes en cours d'examen",        en: 'Pending applications'       },
    approvals:           { fr: 'Approbations',                      en: 'Approvals'                  },
    approvalsSub:        { fr: 'Volume total débloqué',             en: 'Total amount approved'      },
    avgRate:             { fr: 'Taux Moyen',                        en: 'Avg. Rate'                  },
    avgRateSub:          { fr: 'Taux directeur actuel TMM+',        en: 'Current benchmark rate TMM+' },
    // Security notice
    securityTitle:       { fr: 'Vérification Kadastra™',            en: 'Kadastra™ Verification'     },
    securityDesc:        { fr: 'Toutes les données affichées sont cryptées et vérifiées par notre protocole de sécurité. Dernière mise à jour : il y a quelques instants.', en: 'All displayed data is encrypted and verified by our security protocol. Last updated: moments ago.' },
    statusOk:            { fr: 'STATUS: OPÉRATIONNEL',              en: 'STATUS: OPERATIONAL'        },
    loadingError:        { fr: 'Erreur de chargement',              en: 'Loading Error'              },
  },

  // ── Listing Card ───────────────────────────────────────────────────────────
  card: {
    priceOnRequest: { fr: 'Prix à consulter', en: 'Price on request' },
    askAI:          { fr: 'Ask AI',           en: 'Ask AI'           },
    analyzeWith:    { fr: 'Analyser avec Kadastra AI', en: 'Analyze with Kadastra AI' },
  },

  // ── Listing Modal ──────────────────────────────────────────────────────────
  modal: {
    totalPrice:     { fr: 'Prix Total',             en: 'Total Price'       },
    location:       { fr: 'Localisation',            en: 'Location'          },
    surface:        { fr: 'Surface',                 en: 'Area'              },
    bedrooms:       { fr: 'Chambres',                en: 'Bedrooms'          },
    bathrooms:      { fr: 'Salles de bain',          en: 'Bathrooms'         },
    contact:        { fr: 'Contact',                 en: 'Contact'           },
    description:    { fr: 'Description',             en: 'Description'       },
    radius2km:      { fr: 'Périmètre 2km',           en: '2km Radius'        },
    securityAnalysis: { fr: '🛡️ Analyse de Sécurité',  en: '🛡️ Security Analysis' },
    priceAnalysis:  { fr: 'Analyse de prix · IA Kadastra', en: 'Price Analysis · Kadastra AI' },
    estimatedPrice: { fr: 'Prix estimé par le marché :', en: 'Market estimated price:' },
    avgPrice:       { fr: 'Prix dans la moyenne',    en: 'Average market price' },
    aboveMarket:    { fr: 'au-dessus du marché',     en: 'above market'      },
    belowMarket:    { fr: 'en dessous du marché',    en: 'below market'      },
    generateContract: { fr: '⚖️ Générer un Contrat', en: '⚖️ Generate Contract' },
    analyzeAI:      { fr: '🤖 Analyser avec l\'IA',  en: '🤖 Analyze with AI' },
    viewListing:    { fr: "Consulter l'annonce",     en: 'View Listing'      },
  },

  // ── Filters ────────────────────────────────────────────────────────────────
  filters: {
    title1:         { fr: 'Paramètres',              en: 'Parameters'        },
    title2:         { fr: "D'Analyse",               en: 'Analysis'          },
    subtitle:       { fr: 'CONFIGURER VOTRE RECHERCHE KADASTRA', en: 'CONFIGURE YOUR KADASTRA SEARCH' },
    opportunities:  { fr: 'Opportunités Détectées',  en: 'Opportunities Detected' },
    units:          { fr: 'unités',                  en: 'units'             },
    channel:        { fr: '⚖️ Canal d\'Acquisition', en: '⚖️ Acquisition Channel' },
    assetClass:     { fr: '🏢 Classe d\'Actif',      en: '🏢 Asset Class'    },
    sector:         { fr: '📍 Secteur Géographique', en: '📍 Geographic Sector' },
    budget:         { fr: '🏦 Évaluation Budgétaire (TND)', en: '🏦 Budget Range (TND)' },
    area:           { fr: '📐 Surface d\'Exploitation (m²)', en: '📐 Area (m²)' },
    rooms:          { fr: '🧩 Structure (Chambres)', en: '🧩 Bedrooms'       },
    allChannels:    { fr: 'Filtre Global (Tous)',    en: 'All Sources'       },
    allClasses:     { fr: 'Toutes Classes',          en: 'All Types'         },
    national:       { fr: 'Tunisie (National)',      en: 'Tunisia (National)' },
    all:            { fr: 'TOUS',                    en: 'ALL'               },
    reset:          { fr: '🔄 RÉINITIALISER LES ANALYSES', en: '🔄 RESET FILTERS' },
    min:            { fr: 'Min',                     en: 'Min'               },
    max:            { fr: 'Max',                     en: 'Max'               },
  },

  // ── Pagination ─────────────────────────────────────────────────────────────
  pagination: {
    page:     { fr: 'Page',          en: 'Page'         },
    of:       { fr: 'sur',           en: 'of'           },
    total:    { fr: 'Volume total :', en: 'Total:'      },
    assets:   { fr: 'assets',        en: 'listings'     },
    previous: { fr: 'PRÉCÉDENT',     en: 'PREVIOUS'     },
    next:     { fr: 'SUIVANT',       en: 'NEXT'         },
  },

  // ── Stats bar ──────────────────────────────────────────────────────────────
  stats: {
    total:  { fr: 'Total annonces', en: 'Total listings' },
  },

  // ── Security Map / Market Trend ────────────────────────────────────────────
  map: {
    tabSecurity: { fr: '🛡️ Incidents Sécurité',  en: '🛡️ Security Incidents' },
    tabTrends:   { fr: '📈 Tendances Marché',    en: '📈 Market Trends'      },
    // MarketTrendMap
    propertyType:  { fr: 'Type de bien',          en: 'Property type'         },
    transaction:   { fr: 'Transaction',            en: 'Transaction'           },
    refresh:       { fr: 'Actualiser les données', en: 'Refresh data'          },
    loading:       { fr: '⏳ Chargement des tendances…', en: '⏳ Loading trends…' },
    trend12m:      { fr: 'TENDANCE 12 MOIS',       en: '12-MONTH TREND'        },
    decline:       { fr: '🔴 Baisse',              en: '🔴 Decline'            },
    stable:        { fr: '🟡 Stable',              en: '🟡 Stable'             },
    growth:        { fr: '🟢 Hausse',              en: '🟢 Growth'             },
    estimated:     { fr: '(estimé)',               en: '(estimated)'           },
    current:       { fr: 'Prix actuel',            en: 'Current price'         },
    forecast12m:   { fr: 'Prévu dans 12 mois',     en: 'Forecast in 12 months' },
    regionalEst:   { fr: 'Estimation par moyenne régionale faute de données directes.', en: 'Estimated by regional average due to lack of direct data.' },
    errorLoad:     { fr: 'Impossible de charger les tendances. Vérifiez que le serveur est actif.', en: 'Unable to load trends. Check that the server is running.' },
    // Type options
    apartment:     { fr: 'Appartement',            en: 'Apartment'             },
    house:         { fr: 'Maison / Villa',          en: 'House / Villa'         },
    land:          { fr: 'Terrain',                 en: 'Land'                  },
    commercial:    { fr: 'Local commercial',        en: 'Commercial space'      },
    sale:          { fr: 'Vente',                   en: 'Sale'                  },
    rental:        { fr: 'Location',               en: 'Rental'                },
  },

  // ── Kadastra Chatbot UI ────────────────────────────────────────────────────
  chat: {
    // Header
    title:         { fr: 'Kadastra AI',             en: 'Kadastra AI'           },
    subtitle:      { fr: 'Votre assistant immobilier tunisien', en: 'Your Tunisian real estate assistant' },
    // Welcome card
    normalMode:    { fr: 'Je cherche un logement',  en: 'I\'m looking for a home' },
    normalDesc:    { fr: 'Locataire, étudiant ou primo-accédant', en: 'Renter, student or first-time buyer' },
    expertMode:    { fr: 'J\'investis',             en: 'I\'m investing'        },
    expertDesc:    { fr: 'Analyse financière complète', en: 'Full financial analysis' },
    normalActive:  { fr: 'Mode Normal activé ✅',   en: 'Normal Mode active ✅' },
    normalHint:    { fr: 'Évaluation claire du prix, qualité du quartier, équipements et sécurité. Cliquez', en: 'Clear price evaluation, neighborhood quality, amenities and safety. Click' },
    expertActive:  { fr: 'Mode Expert activé 📊',   en: 'Expert Mode active 📊' },
    expertHint:    { fr: 'IRR, Monte Carlo, rendement locatif et fiscalité optimisée. Attachez une propriété + votre profil investisseur.', en: 'IRR, Monte Carlo, rental yield and optimised tax. Attach a property + your investor profile.' },
    exampleHint:   { fr: 'Essayez : "Meilleures affaires à Sousse sous 300 000 TND"', en: 'Try: "Best deals in Sousse under 300,000 TND"' },
    // Input area
    placeholderNormal: { fr: '🏠 Décrivez le logement recherché…', en: '🏠 Describe the home you\'re looking for…' },
    placeholderExpert: { fr: '📊 Posez une question d\'investissement…', en: '📊 Ask an investment question…' },
    analyzeBtn:    { fr: 'Analyser',                en: 'Analyze'               },
    // Attach menu
    attachMenu:    { fr: 'Joindre',                 en: 'Attach'                },
    attachProperty:{ fr: '🏠 Saisir une propriété', en: '🏠 Enter a property'   },
    attachProfile: { fr: '👤 Profil investisseur',  en: '👤 Investor profile'   },
    switchNormal:  { fr: '🏠 Passer en mode Normal', en: '🏠 Switch to Normal mode' },
    switchExpert:  { fr: '📊 Passer en mode Expert', en: '📊 Switch to Expert mode' },
    // Listing attached
    listingAttached: { fr: '📎 Annonce attachée',   en: '📎 Listing attached'   },
    normalModeBadge: { fr: '🏠 Mode Normal',        en: '🏠 Normal Mode'        },
    expertModeBadge: { fr: '📊 Mode Expert',        en: '📊 Expert Mode'        },
    rentalHint:    { fr: 'Kadastra évaluera le prix, le quartier et les services à proximité.', en: 'Kadastra will evaluate the price, neighborhood and nearby services.' },
    saleHint:      { fr: 'Attachez votre profil investisseur pour une analyse complète.', en: 'Attach your investor profile for a complete analysis.' },
    clickAnalyze:  { fr: 'Cliquez', en: 'Click' },
    clickAnalyze2: { fr: 'Analyser', en: 'Analyze' },
    // Normal result card labels
    priceComparison: { fr: '💰 COMPARAISON DE PRIX', en: '💰 PRICE COMPARISON' },
    listedPrice:   { fr: 'PRIX AFFICHÉ',            en: 'LISTED PRICE'          },
    ourEstimate:   { fr: 'NOTRE ESTIMATION',         en: 'OUR ESTIMATE'          },
    notAvailable:  { fr: 'Non disponible',           en: 'Not available'         },
    vsMarket:      { fr: 'vs marché',                en: 'vs market'             },
    whyEstimate:   { fr: '🔍 POURQUOI CETTE ESTIMATION ?', en: '🔍 WHY THIS ESTIMATE?' },
    neighborhood:  { fr: '📍 QUARTIER',              en: '📍 NEIGHBORHOOD'       },
    amenitiesTitle:{ fr: '🏠 ÉQUIPEMENTS INCLUS',    en: '🏠 INCLUDED AMENITIES' },
    footerLabel:   { fr: 'Kadastra · Analyse consommateur', en: 'Kadastra · Consumer analysis' },
    // Property form
    propFormTitle: { fr: '🏠 Détails de la propriété', en: '🏠 Property Details' },
    propType:      { fr: 'TYPE DE BIEN',             en: 'PROPERTY TYPE'         },
    propLocation:  { fr: 'LOCALISATION (ville / quartier)', en: 'LOCATION (city / neighborhood)' },
    propLocationPh:{ fr: 'ex: Tunis Lac, Sousse Centre…', en: 'e.g. Tunis Lac, Sousse Centre…' },
    propPrice:     { fr: 'PRIX (TND)',               en: 'PRICE (TND)'           },
    propArea:      { fr: 'SURFACE (m²)',             en: 'AREA (m²)'             },
    propRooms:     { fr: 'PIÈCES',                   en: 'ROOMS'                 },
    propBedrooms:  { fr: 'CHAMBRES',                 en: 'BEDROOMS'              },
    propFeatures:  { fr: 'ÉQUIPEMENTS & CARACTÉRISTIQUES', en: 'FEATURES & AMENITIES' },
    attachProperty2: { fr: '✓ Joindre la propriété', en: '✓ Attach property'    },
    // Profile form
    profileTitle:  { fr: '👤 Profil investisseur',   en: '👤 Investor Profile'   },
    budget:        { fr: 'BUDGET TOTAL (TND)',        en: 'TOTAL BUDGET (TND)'    },
    holding:       { fr: 'DURÉE DE DÉTENTION',       en: 'HOLDING PERIOD'        },
    holdingYears:  { fr: 'ans',                      en: 'yrs'                   },
    riskTolerance: { fr: 'TOLÉRANCE AU RISQUE',      en: 'RISK TOLERANCE'        },
    riskLow:       { fr: 'Faible — sécurité prioritaire', en: 'Low — safety first' },
    riskMed:       { fr: 'Moyen — équilibre rendement / risque', en: 'Medium — balanced' },
    riskHigh:      { fr: 'Élevé — rendement maximal', en: 'High — max returns'   },
    situation:     { fr: 'SITUATION',                en: 'SITUATION'             },
    firstBuyer:    { fr: 'Primo-accédant',           en: 'First-time buyer'      },
    newPromoter:   { fr: 'Achat auprès d\'un promoteur neuf', en: 'Buying from new developer' },
    attachProfile2:{ fr: '✓ Joindre le profil',     en: '✓ Attach profile'      },
    // Error / guide
    guideTitle:    { fr: 'Mode guidé',               en: 'Guided mode'           },
    guideDesc:     { fr: 'Remplissez les deux formulaires pour une analyse complète.', en: 'Fill in both forms for a complete analysis.' },
    guideStep1:    { fr: 'Étape 1 — 🏠 Détails de la propriété', en: 'Step 1 — 🏠 Property details' },
    guideStep2:    { fr: 'Étape 2 — 👤 Votre profil investisseur', en: 'Step 2 — 👤 Your investor profile' },
    guideThenClick:{ fr: 'Puis cliquez', en: 'Then click' },
    errorTitle:    { fr: '❌ Erreur d\'analyse',     en: '❌ Analysis error'     },
    validationTitle:{ fr: '⚠️ Données manquantes',   en: '⚠️ Missing data'      },
    noPropertyMsg: { fr: 'Décrivez le bien que vous cherchez (type, localisation, prix) ou attachez une annonce avec le bouton +', en: 'Describe the property you\'re looking for (type, location, price) or attach a listing with the + button' },
  },

  // ── Property features ──────────────────────────────────────────────────────
  features: {
    neuf:            { fr: 'Neuf / récent',    en: 'New / recent'    },
    parking:         { fr: 'Parking',          en: 'Parking'         },
    ascenseur:       { fr: 'Ascenseur',        en: 'Elevator'        },
    meuble:          { fr: 'Meublé',           en: 'Furnished'       },
    balcon_terrasse: { fr: 'Balcon / Terrasse',en: 'Balcony / Terrace'},
    climatisation:   { fr: 'Climatisation',    en: 'Air conditioning' },
    chauffage:       { fr: 'Chauffage',        en: 'Heating'         },
    jardin:          { fr: 'Jardin',           en: 'Garden'          },
    piscine:         { fr: 'Piscine',          en: 'Pool'            },
  },
};

export default translations;
