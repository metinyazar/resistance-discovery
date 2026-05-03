from src.skills.literature_search import build_literature_query, parse_pubmed_xml
from src.types import BiomarkerQuery


def test_build_literature_query_uses_core_term_groups():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")

    built = build_literature_query(query)

    assert '"EGFR"' in built
    assert '"T790M"' in built
    assert '"Gefitinib"' in built or '"gefitinib"' in built
    assert '"NSCLC"' in built or '"nsclc"' in built
    assert '"resistance"' in built


def test_parse_pubmed_xml_extracts_minimal_record():
    xml_text = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>123</PMID>
          <Article>
            <ArticleTitle>EGFR T790M resistance to gefitinib</ArticleTitle>
            <Journal><Title>Journal</Title><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
            <Abstract><AbstractText>EGFR T790M causes resistance to gefitinib in NSCLC.</AbstractText></Abstract>
            <AuthorList><Author><LastName>Smith</LastName><Initials>J</Initials></Author></AuthorList>
          </Article>
        </MedlineCitation>
        <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/example</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """

    records = parse_pubmed_xml(xml_text)

    assert len(records) == 1
    assert records[0].pmid == "123"
    assert records[0].doi == "10.1/example"
    assert "resistance" in records[0].abstract
