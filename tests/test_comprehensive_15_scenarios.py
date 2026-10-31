from pathlib import Path
import pytest
from app.config import DATA_DIR
from app.workspace import workspace_manager
from app.main import generate_extractive_summary, INSUFFICIENT_INFO_MESSAGE, format_context_and_citation_map
from app.document_analyzer import document_analyzer


@pytest.fixture(scope="module")
def user28_ws():
    idx, ret = workspace_manager.get_user_workspace(28)
    return idx, ret


def test_100_employees_validation():
    """Verify all 100 employees from EMP001 to EMP100 are present with valid fields."""
    pdf_path = DATA_DIR / "users" / "28" / "uploads" / "Employee_Database_100_Employees.pdf"
    assert pdf_path.exists()
    analysis = document_analyzer.analyze_file(pdf_path)
    assert len(analysis.entities) == 100, f"Expected 100 employees, got {len(analysis.entities)}"

    for i in range(1, 101):
        eid = f"EMP{i:03d}"
        assert eid in analysis.entities, f"Missing {eid}"
        rec = analysis.entities[eid]
        assert rec.record_id == eid
        assert rec.data.get("Name") and len(rec.data["Name"].strip()) > 0
        assert isinstance(rec.data.get("Experience"), (int, float))
        assert isinstance(rec.data.get("Projects Completed"), (int, float))
        assert rec.data.get("Department") and len(rec.data["Department"].strip()) > 0
        assert rec.page in [1, 2, 3, 4, 5, 6]


def test_scenario_01_history_emp001(user28_ws):
    _, ret = user28_ws
    q = "History of EMP001"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP001" in ans
    assert "Aman Aggarwal" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 1


def test_scenario_02_history_emp002(user28_ws):
    _, ret = user28_ws
    q = "History of EMP002"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP002" in ans
    assert "Harsh Verma" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 1


def test_scenario_03_history_emp003(user28_ws):
    _, ret = user28_ws
    q = "History of EMP003"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP003" in ans
    assert "Sneha Meena" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 1


def test_scenario_04_details_emp025(user28_ws):
    _, ret = user28_ws
    q = "Complete details of EMP025"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP025" in ans
    assert "Chirag Saini" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 2


def test_scenario_05_details_emp050(user28_ws):
    _, ret = user28_ws
    q = "Complete details of EMP050"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP050" in ans
    assert "Sakshi Malhotra" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 3


def test_scenario_06_details_emp070(user28_ws):
    _, ret = user28_ws
    q = "Complete details of EMP070"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP070" in ans
    assert "Rohan Rao" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 4


def test_scenario_07_details_emp100(user28_ws):
    _, ret = user28_ws
    q = "Show me the history of EMP100"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP100" in ans
    assert "Sanya Thakur" in ans
    assert "| Field | Details |" in ans
    assert len(cits) == 1 and cits[0].page == 6


def test_scenario_08_experience_emp002(user28_ws):
    _, ret = user28_ws
    q = "What is the experience of EMP002?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP002" in ans
    assert "Harsh Verma" in ans
    assert "15 years" in ans
    assert len(cits) == 1 and cits[0].page == 1


def test_scenario_09_compare_emp001_and_emp002(user28_ws):
    _, ret = user28_ws
    q = "Compare EMP001 and EMP002"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "| Field | EMP001 | EMP002 |" in ans
    assert "Aman Aggarwal" in ans
    assert "Harsh Verma" in ans
    assert len(cits) >= 1


def test_scenario_10_compare_emp025_and_emp050(user28_ws):
    _, ret = user28_ws
    q = "Compare EMP025 and EMP050"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "| Field | EMP025 | EMP050 |" in ans
    assert "Chirag Saini" in ans
    assert "Sakshi Malhotra" in ans
    assert len(cits) >= 2


def test_scenario_11_highest_experience(user28_ws):
    _, ret = user28_ws
    q = "Who has the highest experience?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "Rohan Rao" in ans
    assert "EMP070" in ans
    assert "18 years" in ans
    assert len(cits) >= 1 and cits[0].page == 4


def test_scenario_12_top_10_projects(user28_ws):
    _, ret = user28_ws
    q = "Show the top 10 employees by projects completed"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "| Rank | Employee ID | Name | Department | Projects Completed | Experience |" in ans
    assert "EMP051" in ans
    assert "Rahul Shinde" in ans
    assert "43" in ans
    rows = [l for l in ans.splitlines() if l.startswith("|") and not l.startswith("| Rank") and not l.startswith("| :---")]
    assert len(rows) == 10


def test_scenario_13_average_experience(user28_ws):
    _, ret = user28_ws
    q = "Calculate the average experience of all employees"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "5.45 years" in ans
    assert "Average Experience" in ans
    assert "Total Employees Evaluated" in ans
    assert "100" in ans
    assert len(cits) >= 1


def test_scenario_14_non_existent_emp999(user28_ws):
    _, ret = user28_ws
    q = "Give details of EMP999, which does not exist"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "Employee ID 'EMP999' not found in uploaded documents." in ans
    assert len(cits) == 0


def test_scenario_15_missing_field(user28_ws):
    _, ret = user28_ws
    q = "What is the passport number of EMP002?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "Passport Number" in ans
    assert "not available in the uploaded document" in ans
    assert "EMP002" in ans
    assert "Harsh Verma" in ans
    assert len(cits) == 1 and cits[0].page == 1


def test_scenario_16_compare_experience_emp010_and_emp020(user28_ws):
    _, ret = user28_ws
    q = "Who has more experience, EMP010 or EMP020?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)
    assert "EMP010" in ans
    assert "EMP020" in ans
    assert "| Field | EMP010 | EMP020 |" in ans
