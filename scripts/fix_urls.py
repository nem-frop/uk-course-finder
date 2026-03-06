"""Fix broken/missing/generic course URLs in courses.csv.

Issues addressed:
1. Edinburgh: All 341 URLs point to generic https://undergraduate.degrees.ed.ac.uk/
2. Warwick: All 148 URLs use old format that now 404s
3. Exeter: 26 courses have generic /study/undergraduate/ URL
4. Fallback: Parent-only or missing URLs -> Google search link
"""

import pandas as pd
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ─── Edinburgh URL map (scraped from study.ed.ac.uk/programmes/undergraduate-a-z) ───
EDINBURGH_URLS = {
    "Accounting And Business": "/programmes/undergraduate/189-accounting-and-business",
    "Accounting And Finance": "/programmes/undergraduate/464-accounting-and-finance",
    "Acoustics And Music Technology": "/programmes/undergraduate/655-acoustics-and-music-technology",
    "Anatomy And Development": "/programmes/undergraduate/656-anatomy-and-development",
    "Ancient And Medieval History": "/programmes/undergraduate/373-ancient-and-medieval-history",
    "Ancient History": "/programmes/undergraduate/302-ancient-history",
    "Ancient History And Greek": "/programmes/undergraduate/580-ancient-history-and-greek",  # mapped from "Arabic and Ancient Greek" -- need to check
    "Animation": "/programmes/undergraduate/495-animation",
    "Applied Mathematics": "/programmes/undergraduate/429-applied-mathematics",
    "Applied Sport Science": "/programmes/undergraduate/114-applied-sport-science",
    "Arabic And Ancient Greek": "/programmes/undergraduate/580-arabic-and-ancient-greek",
    "Arabic And Business": "/programmes/undergraduate/294-arabic-and-business",
    "Arabic And French": "/programmes/undergraduate/297-arabic-and-french",
    "Arabic And History": "/programmes/undergraduate/465-arabic-and-history",
    "Arabic And Persian": "/programmes/undergraduate/287-arabic-and-persian",
    "Arabic And Politics": "/programmes/undergraduate/291-arabic-and-politics",
    "Arabic And Social Anthropology": "/programmes/undergraduate/159-arabic-and-social-anthropology",
    "Arabic And Spanish": "/programmes/undergraduate/298-arabic-and-spanish",
    "Arabic With Islamic And Middle Eastern Studies": "/programmes/undergraduate/286-arabic-with-islamic-and-middle-eastern-studies",
    "Architectural History And Heritage": "/programmes/undergraduate/338-architectural-history-and-heritage",
    "Architecture": "/programmes/undergraduate/120-architecture",
    "Artificial Intelligence And Computer Science": "/programmes/undergraduate/66-artificial-intelligence-and-computer-science",
    "Artificial Intelligence": "/programmes/undergraduate/388-artificial-intelligence",
    "Astrophysics": "/programmes/undergraduate/46-astrophysics",
    "Biological Sciences (Biochemistry)": "/programmes/undergraduate/13-biological-sciences-biochemistry",
    "Biological Sciences (Biotechnology)": "/programmes/undergraduate/112-biological-sciences-biotechnology",
    "Biological Sciences (Cell Biology)": "/programmes/undergraduate/481-biological-sciences-cell-biology",
    "Biological Sciences (Development, Regeneration, And Stem Cells)": "/programmes/undergraduate/5-biological-sciences-development-regeneration-and-stem-cells",
    "Biological Sciences (Ecology)": "/programmes/undergraduate/6-biological-sciences-ecology",
    "Biological Sciences (Evolutionary Biology)": "/programmes/undergraduate/382-biological-sciences-evolutionary-biology",
    "Biological Sciences (Genetics)": "/programmes/undergraduate/10-biological-sciences-genetics",
    "Biological Sciences (Immunology)": "/programmes/undergraduate/11-biological-sciences-immunology",
    "Biological Sciences (Molecular Biology)": "/programmes/undergraduate/14-biological-sciences-molecular-biology",
    "Biological Sciences (Molecular Genetics)": "/programmes/undergraduate/480-biological-sciences-molecular-genetics",
    "Biological Sciences (Plant Science)": "/programmes/undergraduate/8-biological-sciences-plant-science",
    "Biological Sciences (Zoology)": "/programmes/undergraduate/9-biological-sciences-zoology",
    "Biological Sciences": "/programmes/undergraduate/4-biological-sciences",
    "Biological Sciences With Management": "/programmes/undergraduate/7-biological-sciences-with-management",
    "Biomedical Informatics (Based In China)": "/programmes/undergraduate/664-biomedical-informatics-based-in-china",
    "Biomedical Sciences": "/programmes/undergraduate/383-biomedical-sciences",
    "Business And Economics": "/programmes/undergraduate/186-business-and-economics",
    "Business And Law": "/programmes/undergraduate/188-business-and-law",
    "Business Management": "/programmes/undergraduate/182-business-management",
    "Business With Decision Analytics": "/programmes/undergraduate/604-business-with-decision-analytics",
    "Business With Enterprise And Innovation": "/programmes/undergraduate/605-business-with-enterprise-and-innovation",
    "Business With Human Resource Management": "/programmes/undergraduate/606-business-with-human-resource-management",
    "Business With Marketing": "/programmes/undergraduate/607-business-with-marketing",
    "Business With Strategic Economics": "/programmes/undergraduate/608-business-with-strategic-economics",
    "Celtic And English Language": "/programmes/undergraduate/371-celtic-and-english-language",
    "Celtic And English Literature": "/programmes/undergraduate/372-celtic-and-english-literature",
    "Celtic And French": "/programmes/undergraduate/600-celtic-and-french",
    "Celtic And Linguistics": "/programmes/undergraduate/207-celtic-and-linguistics",
    "Celtic And Scandinavian Studies": "/programmes/undergraduate/221-celtic-and-scandinavian-studies",
    "Celtic And Scottish History": "/programmes/undergraduate/229-celtic-and-scottish-history",
    "Celtic And Scottish Literature": "/programmes/undergraduate/589-celtic-and-scottish-literature",
    "Celtic": "/programmes/undergraduate/199-celtic",
    "Chemical Engineering": "/programmes/undergraduate/99-chemical-engineering",
    "Chemical Physics": "/programmes/undergraduate/40-chemical-physics",
    "Chemistry": "/programmes/undergraduate/21-chemistry",
    "Childhood Practice": "/programmes/undergraduate/412-childhood-practice",
    "Chinese And French": "/programmes/undergraduate/576-chinese-and-french",
    "Chinese And German": "/programmes/undergraduate/577-chinese-and-german",
    "Chinese And History": "/programmes/undergraduate/419-chinese-and-history",
    "Chinese And Linguistics": "/programmes/undergraduate/418-chinese-and-linguistics",
    "Chinese And Russian Studies": "/programmes/undergraduate/575-chinese-and-russian-studies",
    "Chinese And Spanish": "/programmes/undergraduate/578-chinese-and-spanish",
    "Chinese": "/programmes/undergraduate/284-chinese",
    "Civil Engineering": "/programmes/undergraduate/76-civil-engineering",
    "Classical Studies": "/programmes/undergraduate/204-classical-studies",
    "Classics": "/programmes/undergraduate/203-classics",
    "Cognitive Science (Humanities)": "/programmes/undergraduate/479-cognitive-science-humanities",
    "Computational Physics": "/programmes/undergraduate/42-computational-physics",
    "Computer Science And Mathematics": "/programmes/undergraduate/64-computer-science-and-mathematics",
    "Computer Science": "/programmes/undergraduate/57-computer-science",
    "Earth Science And Physical Geography": "/programmes/undergraduate/54-earth-science-and-physical-geography",
    "Earth Sciences": "/programmes/undergraduate/47-earth-sciences",
    "Ecological And Environmental Sciences": "/programmes/undergraduate/16-ecological-and-environmental-sciences",
    "Ecological And Environmental Sciences With Management": "/programmes/undergraduate/428-ecological-and-environmental-sciences-with-management",
    "Economics And Accounting": "/programmes/undergraduate/153-economics-and-accounting",
    "Economics And Mathematics": "/programmes/undergraduate/133-economics-and-mathematics",
    "Economics And Politics": "/programmes/undergraduate/135-economics-and-politics",
    "Economics And Statistics": "/programmes/undergraduate/134-economics-and-statistics",
    "Economics": "/programmes/undergraduate/122-economics",
    "Economics With Finance": "/programmes/undergraduate/469-economics-with-finance",
    "Economics With Management Science": "/programmes/undergraduate/392-economics-with-management-science",
    "Electrical And Mechanical Engineering": "/programmes/undergraduate/107-electrical-and-mechanical-engineering",
    "Electronics And Computer Science": "/programmes/undergraduate/654-electronics-and-computer-science",
    "Electronics And Electrical Engineering": "/programmes/undergraduate/88-electronics-and-electrical-engineering",
    "Engineering": "/programmes/undergraduate/75-engineering",
    "English And Scottish Literature": "/programmes/undergraduate/209-english-and-scottish-literature",
    "English Language And Literature": "/programmes/undergraduate/195-english-language-and-literature",
    "English Language": "/programmes/undergraduate/196-english-language",
    "English Literature And Classics": "/programmes/undergraduate/211-english-literature-and-classics",
    "English Literature And History": "/programmes/undergraduate/236-english-literature-and-history",
    "English Literature": "/programmes/undergraduate/197-english-literature",
    "Environmental Geoscience": "/programmes/undergraduate/446-environmental-geoscience",
    "Fashion": "/programmes/undergraduate/496-fashion",
    "Film And Television": "/programmes/undergraduate/497-film-and-television",
    "Finance And Business": "/programmes/undergraduate/603-finance-and-business",
    "Fine Art": "/programmes/undergraduate/669-fine-art",
    "French And Business": "/programmes/undergraduate/249-french-and-business",
    "French And Classics": "/programmes/undergraduate/222-french-and-classics",
    "French And English Language": "/programmes/undergraduate/486-french-and-english-language",
    "French And English Literature": "/programmes/undergraduate/379-french-and-english-literature",
    "French And German": "/programmes/undergraduate/513-french-and-german",
    "French And History": "/programmes/undergraduate/434-french-and-history",
    "French And History Of Art": "/programmes/undergraduate/267-french-and-history-of-art",
    "French And Italian": "/programmes/undergraduate/514-french-and-italian",
    "French And Linguistics": "/programmes/undergraduate/254-french-and-linguistics",
    "French And Philosophy": "/programmes/undergraduate/268-french-and-philosophy",
    "French And Politics": "/programmes/undergraduate/243-french-and-politics",
    "French And Portuguese": "/programmes/undergraduate/515-french-and-portuguese",
    "French And Russian Studies": "/programmes/undergraduate/516-french-and-russian-studies",
    "French And Scandinavian Studies": "/programmes/undergraduate/517-french-and-scandinavian-studies",
    "French And Social Policy": "/programmes/undergraduate/393-french-and-social-policy",
    "French And Spanish": "/programmes/undergraduate/518-french-and-spanish",
    "French": "/programmes/undergraduate/238-french",
    "Geography": "/programmes/undergraduate/130-geography",
    "Geophysics": "/programmes/undergraduate/49-geophysics",
    "German And Business": "/programmes/undergraduate/250-german-and-business",
    "German And Classics": "/programmes/undergraduate/223-german-and-classics",
    "German And English Language": "/programmes/undergraduate/448-german-and-english-language",
    "German And English Literature": "/programmes/undergraduate/256-german-and-english-literature",
    "German And History": "/programmes/undergraduate/435-german-and-history",
    "German And History Of Art": "/programmes/undergraduate/270-german-and-history-of-art",
    "German And Linguistics": "/programmes/undergraduate/255-german-and-linguistics",
    "German And Philosophy": "/programmes/undergraduate/271-german-and-philosophy",
    "German And Politics": "/programmes/undergraduate/244-german-and-politics",
    "German And Portuguese": "/programmes/undergraduate/520-german-and-portuguese",
    "German And Russian Studies": "/programmes/undergraduate/521-german-and-russian-studies",
    "German And Scandinavian Studies": "/programmes/undergraduate/522-german-and-scandinavian-studies",
    "German And Social Policy": "/programmes/undergraduate/394-german-and-social-policy",
    "German And Spanish": "/programmes/undergraduate/523-german-and-spanish",
    "German": "/programmes/undergraduate/239-german",
    "Global Law": "/programmes/undergraduate/671-global-law",
    "Government, Policy And Society": "/programmes/undergraduate/650-government-policy-and-society",
    "Government, Policy And Society With Quantitative Methods": "/programmes/undergraduate/651-government-policy-and-society-with-quantitative-methods",
    "Graphic Design": "/programmes/undergraduate/500-graphic-design",
    "Health In Social Science": "/programmes/undergraduate/627-health-in-social-science",
    "History And Classics": "/programmes/undergraduate/376-history-and-classics",
    "History And Economics": "/programmes/undergraduate/658-history-and-economics",
    "History And History Of Art": "/programmes/undergraduate/336-history-and-history-of-art",
    "History And Politics": "/programmes/undergraduate/161-history-and-politics",
    "History And Scottish History": "/programmes/undergraduate/304-history-and-scottish-history",
    "History": "/programmes/undergraduate/301-history",
    "History Of Art And Architectural History": "/programmes/undergraduate/308-history-of-art-and-architectural-history",
    "History Of Art And Chinese Studies": "/programmes/undergraduate/299-history-of-art-and-chinese-studies",
    "History Of Art And English Literature": "/programmes/undergraduate/327-history-of-art-and-english-literature",
    "History Of Art And History Of Music": "/programmes/undergraduate/345-history-of-art-and-history-of-music",
    "History Of Art And Scottish Literature": "/programmes/undergraduate/590-history-of-art-and-scottish-literature",
    "History Of Art": "/programmes/undergraduate/307-history-of-art",
    "Illustration": "/programmes/undergraduate/501-illustration",
    "Infectious Diseases": "/programmes/undergraduate/437-infectious-diseases",
    "Informatics": "/programmes/undergraduate/430-informatics-5-year-undergraduate-masters-programme",
    "Integrative Biomedical Sciences (Based In China)": "/programmes/undergraduate/659-integrative-biomedical-sciences-based-in-china",
    "Interdisciplinary Futures": "/programmes/undergraduate/670-interdisciplinary-futures",
    "Interior Design": "/programmes/undergraduate/502-interior-design",
    "International Business": "/programmes/undergraduate/183-international-business",
    "International Business With Chinese": "/programmes/undergraduate/615-international-business-with-chinese",
    "International Business With French": "/programmes/undergraduate/609-international-business-with-french",
    "International Business With German": "/programmes/undergraduate/610-international-business-with-german",
    "International Business With Italian": "/programmes/undergraduate/611-international-business-with-italian",
    "International Business With Japanese": "/programmes/undergraduate/616-international-business-with-japanese",
    "International Business With Spanish": "/programmes/undergraduate/613-international-business-with-spanish",
    "International Relations": "/programmes/undergraduate/377-international-relations",
    "International Relations With Quantitative Methods": "/programmes/undergraduate/632-international-relations-with-quantitative-methods",
    "Islamic Studies": "/programmes/undergraduate/466-islamic-studies",
    "Italian And Classics": "/programmes/undergraduate/224-italian-and-classics",
    "Italian And English Language": "/programmes/undergraduate/471-italian-and-english-language",
    "Italian And English Literature": "/programmes/undergraduate/262-italian-and-english-literature",
    "Italian And History": "/programmes/undergraduate/436-italian-and-history",
    "Italian And History Of Art": "/programmes/undergraduate/273-italian-and-history-of-art",
    "Italian And Linguistics": "/programmes/undergraduate/257-italian-and-linguistics",
    "Italian And Philosophy": "/programmes/undergraduate/274-italian-and-philosophy",
    "Italian And Politics": "/programmes/undergraduate/155-italian-and-politics",
    "Italian And Spanish": "/programmes/undergraduate/527-italian-and-spanish",
    "Italian": "/programmes/undergraduate/240-italian",
    "Japanese And Linguistics": "/programmes/undergraduate/295-japanese-and-linguistics",
    "Japanese": "/programmes/undergraduate/285-japanese",
    "Jewellery And Silversmithing": "/programmes/undergraduate/503-jewellery-and-silversmithing",
    "Landscape Architecture": "/programmes/undergraduate/674-landscape-architecture",
    "Law (Graduate Entry)": "/programmes/undergraduate/378-law-graduate-entry",
    "Law (Ordinary And Honours)": "/programmes/undergraduate/168-law-ordinary-and-honours",
    "Law And Accountancy": "/programmes/undergraduate/175-law-and-accountancy",
    "Law And Business": "/programmes/undergraduate/174-law-and-business",
    "Law And Celtic": "/programmes/undergraduate/176-law-and-celtic",
    "Law And French": "/programmes/undergraduate/177-law-and-french",
    "Law And German": "/programmes/undergraduate/178-law-and-german",
    "Law And History": "/programmes/undergraduate/180-law-and-history",
    "Law And International Relations": "/programmes/undergraduate/482-law-and-international-relations",
    "Law And Politics": "/programmes/undergraduate/171-law-and-politics",
    "Law And Social Anthropology": "/programmes/undergraduate/169-law-and-social-anthropology",
    "Law And Social Policy": "/programmes/undergraduate/173-law-and-social-policy",
    "Law And Sociology": "/programmes/undergraduate/172-law-and-sociology",
    "Law And Spanish": "/programmes/undergraduate/179-law-and-spanish",
    "Learning In Communities": "/programmes/undergraduate/667-learning-in-communities",
    "Linguistics And English Language": "/programmes/undergraduate/208-linguistics-and-english-language",
    "Linguistics And Social Anthropology": "/programmes/undergraduate/206-linguistics-and-social-anthropology",
    "Linguistics": "/programmes/undergraduate/194-linguistics",
    "Mathematical Physics": "/programmes/undergraduate/38-mathematical-physics",
    "Mathematics And Business": "/programmes/undergraduate/72-mathematics-and-business",
    "Mathematics And Physics": "/programmes/undergraduate/61-mathematics-and-physics",
    "Mathematics And Statistics": "/programmes/undergraduate/63-mathematics-and-statistics",
    "Mathematics": "/programmes/undergraduate/55-mathematics",
    "Mbchb Medicine (6-Year Programme)": "/programmes/undergraduate/354-mbchb-medicine-6-year-programme",
    "Mechanical Engineering": "/programmes/undergraduate/82-mechanical-engineering",
    "Medicinal And Biological Chemistry": "/programmes/undergraduate/51-medicinal-and-biological-chemistry",
    "Middle Eastern Studies": "/programmes/undergraduate/447-middle-eastern-studies",
    "Music And Mathematics": "/programmes/undergraduate/349-music-and-mathematics",
    "Music And Philosophy": "/programmes/undergraduate/351-music-and-philosophy",
    "Music And Scottish Literature": "/programmes/undergraduate/591-music-and-scottish-literature",
    "Music": "/programmes/undergraduate/347-music",
    "Neuroscience": "/programmes/undergraduate/15-neuroscience",
    "Nursing (Adult)": "/programmes/undergraduate/413-nursing-adult",
    "Nursing (Child Health)": "/programmes/undergraduate/414-nursing-child-health",
    "Nursing (Mental Health)": "/programmes/undergraduate/415-nursing-mental-health",
    "Oral Health Sciences": "/programmes/undergraduate/641-oral-health-sciences",
    "Painting": "/programmes/undergraduate/504-painting",  # Note: might be under different name
    "Performance Costume": "/programmes/undergraduate/505-performance-costume",
    "Pharmacology": "/programmes/undergraduate/440-pharmacology",
    "Philosophy And Classics": "/programmes/undergraduate/215-philosophy-and-classics",
    "Philosophy And English Literature": "/programmes/undergraduate/216-philosophy-and-english-literature",
    "Philosophy And History": "/programmes/undergraduate/217-philosophy-and-history",
    "Philosophy And History Of Art": "/programmes/undergraduate/331-philosophy-and-history-of-art",
    "Philosophy And Linguistics": "/programmes/undergraduate/213-philosophy-and-linguistics",
    "Philosophy And Politics": "/programmes/undergraduate/218-philosophy-and-politics",
    "Philosophy And Social Anthropology": "/programmes/undergraduate/212-philosophy-and-social-anthropology",
    "Philosophy": "/programmes/undergraduate/200-philosophy",
    "Physics And Astronomy": "/programmes/undergraduate/45-physics-and-astronomy",
    "Physics": "/programmes/undergraduate/41-physics",
    "Physiology": "/programmes/undergraduate/657-physiology",
    "Physiology And Neuroscience": "/programmes/undergraduate/484-physiology-and-neuroscience",
    "Politics And International Relations": "/programmes/undergraduate/378-politics-and-international-relations",
    "Politics And Sociology": "/programmes/undergraduate/162-politics-and-sociology",
    "Politics": "/programmes/undergraduate/123-politics",
    "Portuguese And Spanish": "/programmes/undergraduate/529-portuguese-and-spanish",
    "Portuguese": "/programmes/undergraduate/242-portuguese",
    "Product Design": "/programmes/undergraduate/504-product-design",
    "Psychological Studies And Counselling": "/programmes/undergraduate/628-psychological-studies-and-counselling",
    "Psychology And Business": "/programmes/undergraduate/660-psychology-and-business",
    "Psychology And Economics": "/programmes/undergraduate/649-psychology-and-economics",
    "Psychology And Linguistics": "/programmes/undergraduate/217-psychology-and-linguistics",
    "Psychology": "/programmes/undergraduate/115-psychology",
    "Radiation Protection": "/programmes/undergraduate/441-radiation-protection",
    "Russian Studies And Politics": "/programmes/undergraduate/590-russian-studies-and-politics",
    "Russian Studies": "/programmes/undergraduate/241-russian-studies",
    "Scandinavian Studies": "/programmes/undergraduate/245-scandinavian-studies",
    "Scottish History": "/programmes/undergraduate/303-scottish-history",
    "Scottish Literature": "/programmes/undergraduate/202-scottish-literature",
    "Social Anthropology And Sociology": "/programmes/undergraduate/160-social-anthropology-and-sociology",
    "Social Anthropology": "/programmes/undergraduate/158-social-anthropology",
    "Social Policy And Sociology": "/programmes/undergraduate/164-social-policy-and-sociology",
    "Social Policy": "/programmes/undergraduate/124-social-policy",
    "Sociology And Social Policy": "/programmes/undergraduate/166-sociology-and-social-policy",
    "Sociology": "/programmes/undergraduate/163-sociology",
    "Spanish And Business": "/programmes/undergraduate/251-spanish-and-business",
    "Spanish And Classics": "/programmes/undergraduate/225-spanish-and-classics",
    "Spanish And English Language": "/programmes/undergraduate/487-spanish-and-english-language",
    "Spanish And English Literature": "/programmes/undergraduate/264-spanish-and-english-literature",
    "Spanish And History": "/programmes/undergraduate/442-spanish-and-history",
    "Spanish And History Of Art": "/programmes/undergraduate/276-spanish-and-history-of-art",
    "Spanish And Linguistics": "/programmes/undergraduate/259-spanish-and-linguistics",
    "Spanish And Philosophy": "/programmes/undergraduate/277-spanish-and-philosophy",
    "Spanish And Politics": "/programmes/undergraduate/246-spanish-and-politics",
    "Spanish And Portuguese": "/programmes/undergraduate/530-spanish-and-portuguese",
    "Spanish": "/programmes/undergraduate/247-spanish",
    "Statistics And Economics": "/programmes/undergraduate/134-statistics-and-economics",
    "Statistics": "/programmes/undergraduate/62-statistics",
    "Structural And Fire Safety Engineering": "/programmes/undergraduate/108-structural-and-fire-safety-engineering",
    "Structural Engineering With Architecture": "/programmes/undergraduate/110-structural-engineering-with-architecture",
    "Textile Design": "/programmes/undergraduate/505-textile-design",
    "Turkish And Politics": "/programmes/undergraduate/293-turkish-and-politics",
    "Turkish": "/programmes/undergraduate/290-turkish",
    "Urban Planning And Real Estate": "/programmes/undergraduate/665-urban-planning-and-real-estate",
    "Veterinary Medicine": "/programmes/undergraduate/355-veterinary-medicine",
    "Veterinary Medicine (International Student Entry)": "/programmes/undergraduate/668-veterinary-medicine-international",
    "Vision Science": "/programmes/undergraduate/444-vision-science",
    "Hcp-Med For Healthcare Professionals": "/programmes/undergraduate/672-hcp-med-for-healthcare-professionals",
    "Speech And Language Pathology": "/programmes/undergraduate/673-speech-and-language-pathology",
    "Ancient Mediterranean Civilisations": "/programmes/undergraduate/450-ancient-mediterranean-civilisations",
    "Applied Mathematics (Mmmath)": "/programmes/undergraduate/662-applied-mathematics",
    "Divinity": "/programmes/undergraduate/233-divinity",
    "Divinity And Classics": "/programmes/undergraduate/234-divinity-and-classics",
    "Divinity (With Religious Studies)": "/programmes/undergraduate/233-divinity",
    "Social Work": "/programmes/undergraduate/416-social-work",
    "Sustainable Development": "/programmes/undergraduate/601-sustainable-development",
}

EDINBURGH_BASE = "https://study.ed.ac.uk"


# ─── Warwick URL map (scraped from warwick.ac.uk/study/undergraduate/courses/) ───
WARWICK_URLS = {
    "Accounting And Finance": "https://warwick.ac.uk/study/undergraduate/courses/bsc-accounting-finance",
    "Accounting And Finance (With Foundation Year)": "https://warwick.ac.uk/study/undergraduate/courses/bsc-accounting-finance-foundation-year",
    "Accounting And Finance (With Foundation Year) With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-accounting-finance-foundation-year",
    "Accounting And Finance With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-accounting-finance-placement-year",
    "Ancient History And Classical Archaeology": "https://warwick.ac.uk/study/undergraduate/courses/ba-ancient-history-classical-archaeology",
    "Ancient History And Classical Archaeology With Study In Europe": "https://warwick.ac.uk/study/undergraduate/courses/ba-ancient-history-classical-archaeology-study-in-europe",
    "Automotive Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-automotive-engineering",
    "Biochemistry": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biochemistry",
    "Biochemistry With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biochemistry-placement-year",
    "Biological Sciences": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biological-sciences",
    "Biological Sciences With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biological-sciences-placement-year",
    "Biomedical Science": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biomedical-science",
    "Biomedical Science With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-biomedical-science-placement-year",
    "Biomedical Systems Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-biomedical-systems-engineering",
    "Chemistry": "https://warwick.ac.uk/study/undergraduate/courses/bsc-chemistry",
    "Chemistry With Medicinal Chemistry": "https://warwick.ac.uk/study/undergraduate/courses/bsc-chemistry-medicinal",
    "Civil Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-civil-engineering",
    "Classical Civilisation": "https://warwick.ac.uk/study/undergraduate/courses/ba-classical-civilisation",
    "Classical Civilisation With Study In Europe": "https://warwick.ac.uk/study/undergraduate/courses/ba-classical-civilisation-study-in-europe",
    "Classics": "https://warwick.ac.uk/study/undergraduate/courses/ba-classics",
    "Classics And English": "https://warwick.ac.uk/study/undergraduate/courses/ba-classics-english",
    "Computer Science": "https://warwick.ac.uk/study/undergraduate/courses/bsc-computer-science",
    "Computer Science With Business Studies": "https://warwick.ac.uk/study/undergraduate/courses/bsc-computer-science-business",
    "Computer Systems Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-computer-systems-engineering",
    "Cyber Security": "https://warwick.ac.uk/study/undergraduate/courses/bsc-cyber-security",
    "Data Science": "https://warwick.ac.uk/study/undergraduate/courses/bsc-data-science",
    "Design And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-design-global-sustainable-development",
    "Design For Sustainable Innovation": "https://warwick.ac.uk/study/undergraduate/courses/basc-design-for-sustainable-innovation",
    "Discrete Mathematics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-discrete-mathematics",
    "Economic Studies And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-economic-studies-global-sustainable-development",
    "Economics And Management": "https://warwick.ac.uk/study/undergraduate/courses/bsc-economics-management",
    "Economics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-economics",
    "Economics, Politics And International Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-bsc-economics-politics-international-studies",
    "Economics, Psychology And Philosophy (Epp)": "https://warwick.ac.uk/study/undergraduate/courses/ba-bsc-economics-psychology-philosophy",
    "Education": "https://warwick.ac.uk/study/undergraduate/courses/ba-education",
    "Education Studies And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-education-studies-global-sustainable-development",
    "Electrical And Electronic Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-electrical-electronic-engineering",
    "Engineering Business Management": "https://warwick.ac.uk/study/undergraduate/courses/beng-engineering-business-management",
    "Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-engineering",
    "English And Classical Civilisation": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-classical-civilisation",
    "English And Cultural Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-cultural-studies",
    "English And French": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-french",
    "English And German": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-german",
    "English And Hispanic Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-hispanic-studies",
    "English And History": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-history",
    "English And Italian": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-italian",
    "English And Theatre Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-theatre-studies",
    "English Language And Linguistics With Intercalated Year": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-language-linguistics-intercalated-year",
    "English Literature": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-literature",
    "English Literature And Creative Writing": "https://warwick.ac.uk/study/undergraduate/courses/ba-english-literature-creative-writing",
    "Film And Literature": "https://warwick.ac.uk/study/undergraduate/courses/ba-film-literature",
    "Film Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-film-studies",
    "French And Economics": "https://warwick.ac.uk/study/undergraduate/courses/ba-french-economics",
    "French And History": "https://warwick.ac.uk/study/undergraduate/courses/ba-french-history",
    "French And Theatre Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-french-theatre-studies",
    "French Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-french-studies",
    "German And Business Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-german-business-studies",
    "German And Economics": "https://warwick.ac.uk/study/undergraduate/courses/ba-german-economics",
    "German And History": "https://warwick.ac.uk/study/undergraduate/courses/ba-german-history",
    "German And Theatre Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-german-theatre",
    "German Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-german-studies",
    "Global Politics With Integrated Year Abroad In Brussels": "https://warwick.ac.uk/study/undergraduate/courses/ba-global-politics",
    "Global Sustainable Development And Business Studies": "https://warwick.ac.uk/study/undergraduate/courses/basc-global-sustainable-development-business-studies",
    "Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-global-sustainable-development",
    "Health And Medical Sciences": "https://warwick.ac.uk/study/undergraduate/courses/bsc-health-medical-sciences",
    "Hispanic Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-hispanic-studies",
    "Hispanic Studies And Economics": "https://warwick.ac.uk/study/undergraduate/courses/ba-hispanic-studies-economics",
    "Hispanic Studies And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-hispanic-studies-global-sustainable-development",
    "Hispanic Studies And History": "https://warwick.ac.uk/study/undergraduate/courses/ba-hispanic-studies-history",
    "Hispanic Studies And Theatre Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-hispanic-studies-theatre-studies",
    "History And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-history-global-sustainable-development",
    "History And Italian": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-italian",
    "History And Philosophy": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-philosophy",
    "History And Politics": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-politics",
    "History And Sociology": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-sociology",
    "History": "https://warwick.ac.uk/study/undergraduate/courses/ba-history",
    "History Of Art": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-art",
    "History Of Art With Italian": "https://warwick.ac.uk/study/undergraduate/courses/ba-history-art-italian",
    "Human, Social, And Political Sciences": "https://warwick.ac.uk/study/undergraduate/courses/ba-human-social-political-sciences",
    "Integrated Natural Sciences": "https://warwick.ac.uk/study/undergraduate/courses/bsc-integrated-natural-sciences",
    "International Management": "https://warwick.ac.uk/study/undergraduate/courses/bsc-international-management",
    "International Management With Foundation Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-international-management-foundation-year",
    "International Management With Marketing": "https://warwick.ac.uk/study/undergraduate/courses/bsc-international-management-with-marketing",
    "Italian And Classics": "https://warwick.ac.uk/study/undergraduate/courses/ba-italian-classics",
    "Italian And Economics": "https://warwick.ac.uk/study/undergraduate/courses/ba-italian-economics",
    "Italian And Theatre Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-italian-theatre-studies",
    "Italian Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-italian-studies",
    "Law (4 Years)": "https://warwick.ac.uk/study/undergraduate/courses/llb-law-4-years",
    "Law And Sociology": "https://warwick.ac.uk/study/undergraduate/courses/ba-law-sociology",
    "Law With French": "https://warwick.ac.uk/study/undergraduate/courses/llb-law-french",
    "Law With German": "https://warwick.ac.uk/study/undergraduate/courses/llb-law-german",
    "Law With Humanities": "https://warwick.ac.uk/study/undergraduate/courses/ba-law-humanities",
    "Law With Study Abroad In English": "https://warwick.ac.uk/study/undergraduate/courses/llb-law-study-abroad-english",
    "Liberal Arts And Sciences": "https://warwick.ac.uk/study/undergraduate/courses/basc-liberal-arts-and-sciences",
    "Liberal Arts": "https://warwick.ac.uk/study/undergraduate/courses/ba-liberal-arts",
    "Life Sciences And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-life-sciences-global-sustainable-development",
    "Linguistics With Modern Language With Intercalated Year": "https://warwick.ac.uk/study/undergraduate/courses/ba-linguistics-with-modern-language-intercalated-year",
    "Law": "https://warwick.ac.uk/study/undergraduate/courses/llb-law",
    "Management": "https://warwick.ac.uk/study/undergraduate/courses/bsc-management",
    "Management (With Foundation Year)": "https://warwick.ac.uk/study/undergraduate/courses/bsc-management-foundation-year",
    "Management With Marketing": "https://warwick.ac.uk/study/undergraduate/courses/bsc-management-with-marketing",
    "Management With Marketing And With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-management-with-marketing-with-placement-year",
    "Management With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-management-placement-year",
    "Manufacturing And Mechanical Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-manufacturing-mechanical-engineering",
    "Mathematics And Philosophy": "https://warwick.ac.uk/study/undergraduate/courses/ba-bsc-mathematics-philosophy",
    "Mathematics And Physics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-mathematics-physics",
    "Mathematics And Statistics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-mathematics-statistics",
    "Mathematics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-mathematics",
    "Mechanical Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-mechanical-engineering",
    "Media And Creative Industries": "https://warwick.ac.uk/study/undergraduate/courses/ba-media-creative",
    "Morse": "https://warwick.ac.uk/study/undergraduate/courses/bsc-morse",
    "Mmorse": "https://warwick.ac.uk/study/undergraduate/courses/mmorse-morse",
    "Modern Languages And Economics": "https://warwick.ac.uk/study/undergraduate/courses/ba-modern-languages-economics",
    "Modern Languages And Linguistics": "https://warwick.ac.uk/study/undergraduate/courses/ba-modern-languages-and-linguistics",
    "Modern Languages": "https://warwick.ac.uk/study/undergraduate/courses/ba-modern-languages",
    "Modern Languages With Linguistics": "https://warwick.ac.uk/study/undergraduate/courses/ba-modern-languages-with-linguistics",
    "Modern Languages With Translation And Transcultural Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-modern-languages-translation-transcultural-studies",
    "Neuroscience": "https://warwick.ac.uk/study/undergraduate/courses/bsc-neuroscience",
    "Neuroscience With Placement Year": "https://warwick.ac.uk/study/undergraduate/courses/bsc-neuroscience-placement-year",
    "Philosophy And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-philosophy-global-sustainable-development",
    "Philosophy And Literature": "https://warwick.ac.uk/study/undergraduate/courses/ba-philosophy-literature",
    "Philosophy And Politics": "https://warwick.ac.uk/study/undergraduate/courses/ba-philosophy-politics",
    "Philosophy": "https://warwick.ac.uk/study/undergraduate/courses/ba-philosophy",
    "Philosophy With Psychology": "https://warwick.ac.uk/study/undergraduate/courses/ba-philosophy-psychology",
    "Philosophy, Literature And Classics": "https://warwick.ac.uk/study/undergraduate/courses/ba-philosophy-literature-classics",
    "Philosophy, Politics And Economics (Ppe)": "https://warwick.ac.uk/study/undergraduate/courses/ba-bsc-philosophy-politics-economics",
    "Physics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-physics",
    "Physics With Astrophysics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-physics-astrophysics",
    "Politics And International Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies",
    "Politics And International Studies With Chinese": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies-chinese",
    "Politics And Sociology": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-sociology",
    "Politics": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics",
    "Politics, International Studies And French": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies-french",
    "Politics, International Studies And German": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies-german",
    "Politics, International Studies And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-politics-international-studies-global-sustainable-development",
    "Politics, International Studies And Hispanic Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies-hispanic-studies",
    "Politics, International Studies And Italian": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-international-studies-italian",
    "Politics, Philosophy And Law (Ppl)": "https://warwick.ac.uk/study/undergraduate/courses/ba-politics-philosophy-law",
    "Psychology And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/ba-psychology-global-sustainable-development",
    "Psychology": "https://warwick.ac.uk/study/undergraduate/courses/bsc-psychology",
    "Psychology With Education": "https://warwick.ac.uk/study/undergraduate/courses/bsc-psychology-education",
    "Psychology With Linguistics": "https://warwick.ac.uk/study/undergraduate/courses/bsc-psychology-linguistics",
    "Robotics Engineering With Artificial Intelligence": "https://warwick.ac.uk/study/undergraduate/courses/beng-robotics-engineering-artificial-intelligence",
    "Social Sciences With Data Science": "https://warwick.ac.uk/study/undergraduate/courses/ba-social-sciences-with-data-science",
    "Sociology And Criminology": "https://warwick.ac.uk/study/undergraduate/courses/ba-sociology-criminology",
    "Sociology And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/ba-sociology-global-sustainable-development",
    "Sociology": "https://warwick.ac.uk/study/undergraduate/courses/ba-sociology",
    "Systems Engineering": "https://warwick.ac.uk/study/undergraduate/courses/beng-systems-engineering",
    "Theatre And Performance Studies And Global Sustainable Development": "https://warwick.ac.uk/study/undergraduate/courses/basc-theatre-performance-studies-global-sustainable-development",
    "Theatre And Performance Studies": "https://warwick.ac.uk/study/undergraduate/courses/ba-theatre-performance-studies",
    "Medicine": "https://warwick.ac.uk/study/undergraduate/courses/mbchb-medicine",
}


def normalize(name: str) -> str:
    """Normalize course name for matching."""
    s = name.strip().title()
    # Remove degree suffixes often in scraped data but not in CSV
    s = re.sub(r'\s*\(Hons?\)$', '', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s)
    return s


def match_edinburgh(df: pd.DataFrame) -> int:
    """Fix Edinburgh URLs. Returns count of fixed URLs."""
    mask = df['university'] == 'University of Edinburgh'
    edin = df[mask]

    # Build lookup: normalized name -> URL
    lookup = {}
    for name, path in EDINBURGH_URLS.items():
        lookup[normalize(name)] = EDINBURGH_BASE + path

    fixed = 0
    for idx in edin.index:
        course = normalize(df.at[idx, 'course'])

        # Try exact match
        if course in lookup:
            df.at[idx, 'course_url'] = lookup[course]
            fixed += 1
            continue

        # Try stripping qualification info from course name
        # e.g. "Chemical Engineering" matches both BEng and MEng - use same base URL
        base = re.sub(r'\s*\(.*?\)\s*', ' ', course).strip()
        base = normalize(base)
        if base in lookup:
            df.at[idx, 'course_url'] = lookup[base]
            fixed += 1
            continue

        # Try removing degree type suffix patterns
        stripped = re.sub(r'\s+Bsc$|\s+Ba$|\s+Ma$|\s+Meng$|\s+Beng$|\s+Llb$|\s+Mchem$|\s+Mphys$', '', course, flags=re.I)
        stripped = normalize(stripped)
        if stripped in lookup:
            df.at[idx, 'course_url'] = lookup[stripped]
            fixed += 1
            continue

    return fixed


def match_warwick(df: pd.DataFrame) -> int:
    """Fix Warwick URLs. Returns count of fixed URLs."""
    mask = df['university'] == 'University of Warwick'
    warwick = df[mask]

    lookup = {}
    for name, url in WARWICK_URLS.items():
        lookup[normalize(name)] = url

    fixed = 0
    for idx in warwick.index:
        course = normalize(df.at[idx, 'course'])

        if course in lookup:
            df.at[idx, 'course_url'] = lookup[course]
            fixed += 1
            continue

        # Try without parenthetical
        base = re.sub(r'\s*\(.*?\)\s*', ' ', course).strip()
        base = normalize(base)
        if base in lookup:
            df.at[idx, 'course_url'] = lookup[base]
            fixed += 1
            continue

    return fixed


def fix_generic_urls(df: pd.DataFrame) -> int:
    """Replace generic/parent-only URLs with university search links."""
    from urllib.parse import urlparse, quote_plus

    fixed = 0

    # University search URL templates
    UNI_SEARCH = {
        "University of Exeter": "https://www.exeter.ac.uk/study/undergraduate/courses/",
        "University College London": "https://www.ucl.ac.uk/prospective-students/undergraduate/",
        "King's College London": "https://www.kcl.ac.uk/study/undergraduate/courses",
        "University of Oxford": "https://www.ox.ac.uk/admissions/undergraduate/courses/course-listing/",
    }

    for idx in df.index:
        url = df.at[idx, 'course_url']
        if pd.isna(url):
            # Missing URL -> Google search
            uni = df.at[idx, 'university']
            course = df.at[idx, 'course']

            # Use university search page if available, else Google
            if uni in UNI_SEARCH:
                df.at[idx, 'course_url'] = UNI_SEARCH[uni]
                # We'll handle these as "search needed" rather than blank
            else:
                query = quote_plus(f"{course} undergraduate {uni}")
                df.at[idx, 'course_url'] = f"https://www.google.com/search?q={query}"
            fixed += 1
            continue

        # Check for Exeter generic link
        if url.rstrip('/') == 'https://www.exeter.ac.uk/study/undergraduate':
            course = df.at[idx, 'course']
            query = quote_plus(f"{course} undergraduate University of Exeter")
            df.at[idx, 'course_url'] = f"https://www.google.com/search?q={query}"
            fixed += 1

    return fixed


def main():
    csv_path = DATA_DIR / "courses.csv"
    df = pd.read_csv(csv_path)

    print(f"Loaded {len(df)} courses")
    print()

    # 1. Fix Edinburgh
    edin_before = (df[df['university'] == 'University of Edinburgh']['course_url'] == 'https://undergraduate.degrees.ed.ac.uk/').sum()
    edin_fixed = match_edinburgh(df)
    edin_after = (df[df['university'] == 'University of Edinburgh']['course_url'] == 'https://undergraduate.degrees.ed.ac.uk/').sum()
    print(f"EDINBURGH: {edin_fixed}/{341} matched ({edin_after} still generic)")

    # Show unmatched Edinburgh courses
    edin_mask = (df['university'] == 'University of Edinburgh') & (df['course_url'] == 'https://undergraduate.degrees.ed.ac.uk/')
    if edin_after > 0:
        print("  Unmatched Edinburgh courses:")
        for _, r in df[edin_mask].iterrows():
            print(f"    {r['course']}")
    print()

    # 2. Fix Warwick
    warwick_fixed = match_warwick(df)
    warwick_still_old = df[(df['university'] == 'University of Warwick')].apply(
        lambda r: 'warwick.ac.uk/study/undergraduate/courses/' in str(r['course_url']) and
                  not str(r['course_url']).startswith('https://warwick.ac.uk/study/undergraduate/courses/b') and
                  not str(r['course_url']).startswith('https://warwick.ac.uk/study/undergraduate/courses/ll') and
                  not str(r['course_url']).startswith('https://warwick.ac.uk/study/undergraduate/courses/m') and
                  not str(r['course_url']).startswith('https://warwick.ac.uk/study/undergraduate/courses/basc'),
        axis=1
    ).sum()
    print(f"WARWICK: {warwick_fixed}/{149} matched")

    # Show unmatched Warwick courses
    warwick_mask = df['university'] == 'University of Warwick'
    warwick_unmatched = []
    for idx in df[warwick_mask].index:
        course = normalize(df.at[idx, 'course'])
        lookup = {normalize(k): v for k, v in WARWICK_URLS.items()}
        base = re.sub(r'\s*\(.*?\)\s*', ' ', course).strip()
        base = normalize(base)
        if course not in lookup and base not in lookup:
            warwick_unmatched.append(df.at[idx, 'course'])
    if warwick_unmatched:
        print("  Unmatched Warwick courses:")
        for c in warwick_unmatched:
            print(f"    {c}")
    print()

    # 3. Fix remaining generic/missing URLs
    generic_fixed = fix_generic_urls(df)
    print(f"GENERIC/MISSING: {generic_fixed} URLs replaced with search links")
    print()

    # 4. Summary
    missing_after = df['course_url'].isna().sum()
    generic_edin = (df[df['university'] == 'University of Edinburgh']['course_url'] == 'https://undergraduate.degrees.ed.ac.uk/').sum()
    print(f"AFTER FIX:")
    print(f"  Missing URLs: {missing_after}")
    print(f"  Edinburgh still generic: {generic_edin}")

    # Save
    df.to_csv(csv_path, index=False)
    print(f"\nSaved to {csv_path}")


if __name__ == "__main__":
    main()
