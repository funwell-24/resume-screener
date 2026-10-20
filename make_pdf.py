import pymupdf

doc = pymupdf.open()
page = doc.new_page(width=612, height=792)

lines = [
    "Alice Johnson",
    "alice.johnson@example.com | +1 555 123 4567",
    "",
    "PROFESSIONAL SUMMARY",
    "Senior Python data engineer with 5 years of experience building",
    "ETL pipelines and deploying ML models in production.",
    "",
    "SKILLS",
    "Python, pandas, SQL, Docker, AWS, scikit-learn, Airflow, Spark",
    "",
    "EXPERIENCE",
    "Senior Data Engineer, Acme Corp",
    "Jan 2020 - Present",
    "- Built production ETL pipelines in Python using Airflow",
    "- Deployed ML models to AWS using Docker",
    "- Optimized SQL queries on PostgreSQL",
    "",
    "Data Engineer, Beta Inc",
    "Jun 2018 - Dec 2019",
    "- Developed data pipelines using Python and pandas",
    "",
    "EDUCATION",
    "BSc Computer Science, Example University, 2018",
]

y = 50
for line in lines:
    if line:
        page.insert_text((50, y), line, fontsize=11, fontname="helv")
    y += 16

doc.save("data/resumes/alice.pdf")
doc.close()
print("Created data/resumes/alice.pdf")
