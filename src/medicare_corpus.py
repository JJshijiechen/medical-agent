from langchain_core.documents import Document

from .config import DEFAULT_MEDICARE_GUIDELINE_URLS


OFFLINE_MEDICARE_DOCS = [
    Document(
        page_content=(
            "Medicare Part B covers preventive and screening services that help patients stay healthy, "
            "detect health problems early, and prevent disease. Many preventive services have no patient "
            "cost when the provider accepts assignment."
        ),
        metadata={
            "title": "Medicare Preventive and Screening Services",
            "url": "https://www.medicare.gov/coverage/preventive-screening-services?linkId=134567254",
            "source_type": "offline_sample",
            "topic": "preventive_services",
            "coverage_area": "part_b",
            "year": 2026,
        },
    ),
    Document(
        page_content=(
            "Medicare Part B helps cover medically necessary services to diagnose or treat a medical condition "
            "and preventive services such as flu shots or screenings when clinically appropriate."
        ),
        metadata={
            "title": "What Medicare Part B Covers",
            "url": "https://www.medicare.gov/what-medicare-covers/what-part-b-covers",
            "source_type": "offline_sample",
            "topic": "part_b",
            "coverage_area": "part_b",
            "year": 2026,
        },
    ),
    Document(
        page_content=(
            "Original Medicare does not cover every item or service. Common exclusions include long-term care, "
            "most dental care, hearing aids, routine eye exams for eyeglasses, and cosmetic surgery."
        ),
        metadata={
            "title": "Original Medicare Non-Covered Services",
            "url": "https://www.medicare.gov/providers-services/original-medicare/not-covered",
            "source_type": "offline_sample",
            "topic": "not_covered",
            "coverage_area": "original_medicare",
            "year": 2026,
        },
    ),
    Document(
        page_content=(
            "Medicare coverage can be based on federal and state laws, national coverage decisions from Medicare, "
            "and local coverage decisions made by Medicare Administrative Contractors in each state."
        ),
        metadata={
            "title": "Original Medicare Coverage Factors",
            "url": "https://www.medicare.gov/providers-services/original-medicare",
            "source_type": "offline_sample",
            "topic": "coverage_determination",
            "coverage_area": "original_medicare",
            "year": 2026,
        },
    ),
    Document(
        page_content=(
            "The Initial Preventive Physical Exam, also called the Welcome to Medicare preventive visit, is covered "
            "once within the first 12 months after Part B starts and includes review of medical and social history, "
            "risk factors, preventive service education, BMI, and a simple vision test."
        ),
        metadata={
            "title": "Welcome to Medicare Preventive Visit",
            "url": "https://www.medicare.gov/coverage/preventive-visit-and-yearly-wellness-exams.html",
            "source_type": "offline_sample",
            "topic": "wellness_visit",
            "coverage_area": "part_b",
            "year": 2026,
        },
    ),
]


OFFICIAL_MEDICARE_URLS = list(DEFAULT_MEDICARE_GUIDELINE_URLS)
