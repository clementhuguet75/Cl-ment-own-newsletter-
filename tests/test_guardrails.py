"""Offline deterministic tests: no API key, internet or billable model calls."""
import copy
import unittest
from guardrails import assert_report, inspect_report, compact_for_model, RecoverableDigestError

P = ("L'installation dispose d'une piste de deux kilomètres, mais la présence d'une piste ne prouve pas "
     "que des escadrons puissent y être stationnés durablement. Pour cela, des stocks de carburant, des "
     "installations de maintenance, des abris et des autorisations d'accès restent nécessaires. "
     "La comparaison avec les installations déjà existantes dans la région permet de distinguer "
     "une nouvelle capacité militaire d'un simple signal diplomatique. ")
CANDIDATES=[{"id":i,"publisher":("ISW" if i%2 else "RUSI"),
             "date":f"2026-11-{5-i%4:02d}T10:00:00+00:00",
             "title":"Analyse de la situation régionale",
             "excerpt":"Résumé récent de source authentique",
             "url":f"https://example.org/{i}"} for i in range(45)]

def sample():
    return {
      "title":"Le rôle des infrastructures aériennes en Asie du Sud-Est",
      "subtitle":"Analyse des capacités, limites et effets régionaux",
      "lead":"Un nouvel aérodrome attire l'attention des observateurs militaires, mais sa portée opérationnelle reste limitée.",
      "at_a_glance":["Une inauguration militaire a eu lieu à Ban Keun.",
                     "La piste possède deux kilomètres de longueur.",
                     "Les équipements logistiques restent à documenter."],
      "sections":[
        {"heading":f"Les capacités de la base numéro {n}",
         "body":[P,P],"significance":"Une base ne devient opérationnelle sans les moyens de soutien.",
         "watch":"Contrôler les hangars, dépôts de carburant et annonces d'accès.",
         "source_ids":[n]} for n in (0,1)],
      "maps":[{"title":"Carte originale de contexte","why":"Une localisation géographique","source_id":0}],
      "further_reading":[0,1]
    }

class TestGuardrails(unittest.TestCase):
    def test_complete_article_passes(self):
        self.assertEqual(inspect_report(sample(), CANDIDATES),[])
        assert_report(sample(),CANDIDATES)

    def test_invalid_citation_blocks_publication(self):
        case=sample()
        case["sections"][1]["source_ids"]=[999]
        with self.assertRaises(RecoverableDigestError):
            assert_report(case,CANDIDATES)

    def test_empty_section_cannot_be_published(self):
        case=sample()
        case["sections"][1]["body"]=[]
        self.assertTrue(inspect_report(case,CANDIDATES))

    def test_missing_top_level_field(self):
        case=sample()
        del case["title"]
        self.assertTrue(inspect_report(case,CANDIDATES))

    def test_too_long_is_rejected(self):
        case=sample()
        case["sections"][0]["body"]=[P*25,P*25]
        self.assertTrue(any("Length" in x for x in inspect_report(case,CANDIDATES)))

    def test_incomplete_json_not_a_document(self):
        self.assertTrue(inspect_report("broken json", CANDIDATES))

    def test_publisher_coverage_and_input_size(self):
        chosen=compact_for_model(CANDIDATES)
        self.assertLessEqual(len(chosen),40)
        self.assertEqual({x["publisher"] for x in chosen},{"ISW","RUSI"})
        self.assertTrue(all(len(x["excerpt"])<=310 for x in chosen))

    def test_boolean_not_accepted_as_article_id(self):
        case=sample()
        case["sections"][0]["source_ids"]=[True]
        self.assertTrue(inspect_report(case,CANDIDATES))

if __name__=="__main__":
    unittest.main()
