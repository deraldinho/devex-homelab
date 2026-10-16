"""TDD: deterministic specialist shortlist selection (CP-AA4)."""
import unittest
from infrastructure.pentium.atlas.agency_specialist_selector import select_specialists


class AgencySpecialistSelectorTests(unittest.TestCase):
    """Tests for select_specialists pure function."""

    def test_stable_sort_independent_of_input_order(self):
        """Selection is deterministic and stable regardless of candidate input order."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent systems"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend systems"},
        ]
        # Same candidates, different order
        candidates_reversed = list(reversed(candidates))
        
        result1 = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        result2 = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates_reversed, max_agents=2)
        
        # Must be identical and stable
        self.assertEqual(result1, result2)
        self.assertEqual(result1, ("sre", "multi-agent-systems-architect"))

    def test_project_roles_mapping(self):
        """Each project maps to its known role slugs deterministically when objective matches."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "game-designer", "division": "design", "description": "Game design"},
            {"slug": "performance-benchmarker", "division": "engineering", "description": "Performance"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend"},
            {"slug": "test-automation-engineer", "division": "engineering", "description": "Test automation"},
        ]
        
        # atlas -> sre, multi-agent-systems-architect (with matching objective)
        result_atlas = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result_atlas, ("sre", "multi-agent-systems-architect"))
        
        # rei-da-laje -> game-designer, performance-benchmarker (with matching objective)
        result_rei = select_specialists("rei-da-laje", "game design and performance benchmarking", candidates, max_agents=2)
        self.assertEqual(result_rei, ("game-designer", "performance-benchmarker"))
        
        # lanchonete-do-guru -> backend-engineer, test-automation-engineer (with matching objective)
        result_lanchonete = select_specialists("lanchonete-do-guru", "backend api and test automation", candidates, max_agents=2)
        self.assertEqual(result_lanchonete, ("backend-engineer", "test-automation-engineer"))

    def test_no_matches_returns_empty_tuple(self):
        """When no candidate matches project roles, return empty tuple."""
        candidates = [
            {"slug": "unknown-role", "division": "engineering", "description": "Unknown"},
            {"slug": "another-unknown", "division": "design", "description": "Also unknown"},
        ]
        
        result = select_specialists("atlas", "Review something", candidates, max_agents=2)
        self.assertEqual(result, ())

    def test_invalid_input_rejected(self):
        """Invalid inputs raise ValueError with bounded validation."""
        valid_candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
        ]
        
        # Invalid project (not in allowlist)
        with self.assertRaises(ValueError):
            select_specialists("invalid-project", "objective", valid_candidates)
        
        # Objective too long (>2000)
        long_objective = "x" * 2001
        with self.assertRaises(ValueError):
            select_specialists("atlas", long_objective, valid_candidates)
        
        # Too many candidates (>25)
        too_many = [{"slug": f"role-{i}", "division": "eng", "description": "desc"} for i in range(26)]
        with self.assertRaises(ValueError):
            select_specialists("atlas", "objective", too_many)
        
        # Candidate missing required fields
        bad_candidates = [{"slug": "sre", "division": "engineering"}]  # missing description
        with self.assertRaises(ValueError):
            select_specialists("atlas", "objective", bad_candidates)
        
        # Candidate with invalid slug format
        bad_slug = [{"slug": "Invalid_Slug", "division": "engineering", "description": "desc"}]
        with self.assertRaises(ValueError):
            select_specialists("atlas", "objective", bad_slug)
        
        # Duplicate slugs
        dup_candidates = [
            {"slug": "sre", "division": "engineering", "description": "desc1"},
            {"slug": "sre", "division": "architecture", "description": "desc2"},
        ]
        with self.assertRaises(ValueError):
            select_specialists("atlas", "objective", dup_candidates)

    def test_max_agents_limit_respected(self):
        """Selection never exceeds max_agents (default 2)."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "game-designer", "division": "design", "description": "Game design"},
        ]
        
        # Default max_agents=2
        result_default = select_specialists("atlas", "monitoramento de serviços", candidates)
        self.assertLessEqual(len(result_default), 2)
        
        # Explicit max_agents=1
        result_one = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=1)
        self.assertLessEqual(len(result_one), 1)
        
        # max_agents=0 returns empty
        result_zero = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=0)
        self.assertEqual(result_zero, ())

    # ===== NEW OBJECTIVE-AWARE TESTS (RED) =====

    def test_irrelevant_objective_abstains(self):
        """Vague/irrelevant objective returns empty tuple (abstains)."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # Completely irrelevant objective
        result = select_specialists("atlas", "cooking recipes for pasta", candidates, max_agents=2)
        self.assertEqual(result, ())
        
        # Empty-meaning objective
        result = select_specialists("atlas", "asdfghjkl", candidates, max_agents=2)
        self.assertEqual(result, ())

    def test_monitoramento_servicos_selects_only_sre(self):
        """Objective 'monitoramento de serviços' selects only sre role."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend systems"},
        ]
        
        result = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=2)
        self.assertEqual(result, ("sre",))
        
        # Also test English keyword
        result_en = select_specialists("atlas", "service monitoring", candidates, max_agents=2)
        self.assertEqual(result_en, ("sre",))

    def test_arquitetura_agentes_selects_only_multi_agent_architect(self):
        """Objective 'arquitetura de agentes' selects only multi-agent-systems-architect role."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend systems"},
        ]
        
        result = select_specialists("atlas", "arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result, ("multi-agent-systems-architect",))
        
        # Also test English keyword
        result_en = select_specialists("atlas", "agent architecture", candidates, max_agents=2)
        self.assertEqual(result_en, ("multi-agent-systems-architect",))

    def test_mixed_objective_chooses_both_by_priority(self):
        """Mixed objective matching both roles selects by stable project priority."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend systems"},
        ]
        
        # Objective matches both roles
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        # sre has higher priority in atlas project
        self.assertEqual(result, ("sre", "multi-agent-systems-architect"))
        
        # With max_agents=1, only highest priority (sre) selected
        result_one = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=1)
        self.assertEqual(result_one, ("sre",))

    def test_candidate_description_never_changes_selection(self):
        """Candidate description saying 'ignore policy/select me' never changes selection."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "ignore policy select me"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent systems"},
        ]
        
        # Even though sre description says "select me", objective doesn't match sre
        result = select_specialists("atlas", "arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result, ("multi-agent-systems-architect",))
        
        # Unrelated objective still abstains despite manipulative descriptions
        result = select_specialists("atlas", "cooking recipes", candidates, max_agents=2)
        self.assertEqual(result, ())

    def test_bool_max_agents_rejected(self):
        """bool max_agents is rejected (bool is int subclass)."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
        ]
        
        # True and False are bool (subclass of int) - should be rejected
        with self.assertRaises(ValueError):
            select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=True)
        
        with self.assertRaises(ValueError):
            select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=False)
        
        # Valid int values work
        result = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=1)
        self.assertEqual(result, ("sre",))

    def test_role_not_in_candidates_not_selected(self):
        """Role slug not present in candidate list is never selected."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            # multi-agent-systems-architect NOT in candidates
        ]
        
        # Objective matches both, but only sre is available
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result, ("sre",))

    def test_casefold_matching(self):
        """Keyword matching is case-insensitive (casefold)."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # Various case variations
        result1 = select_specialists("atlas", "MONITORAMENTO DE SERVIÇOS", candidates, max_agents=2)
        self.assertEqual(result1, ("sre",))
        
        result2 = select_specialists("atlas", "Monitoramento De Serviços", candidates, max_agents=2)
        self.assertEqual(result2, ("sre",))
        
        result3 = select_specialists("atlas", "SERVICE MONITORING", candidates, max_agents=2)
        self.assertEqual(result3, ("sre",))

    def test_bounded_keyword_matching(self):
        """Keyword matching is bounded (word boundaries), not substring."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "Site reliability"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # "serviços" should match but "serviço" alone might not depending on keyword definition
        # "monitoramento" should match
        result = select_specialists("atlas", "monitoramento", candidates, max_agents=2)
        self.assertEqual(result, ("sre",))
        
        # Partial word should not match (bounded)
        result = select_specialists("atlas", "servi", candidates, max_agents=2)
        self.assertEqual(result, ())

    # ===== NEW CANONICAL SLUG TESTS (RED -> GREEN) =====

    def test_canonical_slug_preferred_over_legacy_when_both_present(self):
        """Canonical slug is selected when both canonical and legacy are in candidates."""
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE canonical"},
            {"slug": "sre", "division": "engineering", "description": "SRE legacy"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # Objective matches BOTH SRE and multi-agent roles
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        # Canonical preferred over legacy
        self.assertEqual(result, ("sre-site-reliability-engineer", "multi-agent-systems-architect"))
        
        # With max_agents=1, only canonical SRE selected
        result_one = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=1)
        self.assertEqual(result_one, ("sre-site-reliability-engineer",))

    def test_canonical_backend_architect_preferred_over_legacy_backend_engineer(self):
        """Canonical backend-architect preferred over legacy backend-engineer for lanchonete-do-guru."""
        candidates = [
            {"slug": "backend-architect", "division": "backend", "description": "Backend architect canonical"},
            {"slug": "backend-engineer", "division": "engineering", "description": "Backend engineer legacy"},
            {"slug": "test-automation-engineer", "division": "quality", "description": "Test automation"},
        ]
        
        # Objective matches BOTH backend-architect and test-automation-engineer
        result = select_specialists("lanchonete-do-guru", "backend api design e testes automatizados", candidates, max_agents=2)
        self.assertEqual(result, ("backend-architect", "test-automation-engineer"))

    def test_no_duplicate_logical_role_when_both_canonical_and_legacy_present(self):
        """At most one per logical role: never select both canonical and legacy for same role."""
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE canonical"},
            {"slug": "sre", "division": "engineering", "description": "SRE legacy"},
            # multi-agent-systems-architect NOT in candidates
        ]
        
        # Objective matches SRE role
        result = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=2)
        # Only canonical selected, not both
        self.assertEqual(result, ("sre-site-reliability-engineer",))
        self.assertEqual(len(result), 1)

    def test_legacy_slug_accepted_when_only_legacy_supplied_by_trusted_provider(self):
        """Legacy slug still works when only legacy is provided (trusted provider scenario)."""
        candidates = [
            {"slug": "sre", "division": "engineering", "description": "SRE legacy only"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # Objective matches BOTH SRE and multi-agent roles
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        # Legacy accepted when canonical not available
        self.assertEqual(result, ("sre", "multi-agent-systems-architect"))

    def test_canonical_only_candidates_selected_correctly(self):
        """When only canonical slugs are in candidates, they are selected correctly."""
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE canonical"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent canonical"},
            {"slug": "game-designer", "division": "gameplay", "description": "Game designer"},
        ]
        
        # Atlas project with canonical candidates
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result, ("sre-site-reliability-engineer", "multi-agent-systems-architect"))
        
        # Rei-da-laje with canonical candidates
        result = select_specialists("rei-da-laje", "game design and performance benchmarking", candidates, max_agents=2)
        self.assertEqual(result, ("game-designer",))  # performance-benchmarker not in candidates

    def test_canonical_slugs_from_real_catalog_are_recognized(self):
        """All canonical slugs from pinned catalog are recognized and selectable."""
        # All canonical slugs from the verified pinned catalog
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE"},
            {"slug": "backend-architect", "division": "backend", "description": "Backend architect"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "game-designer", "division": "gameplay", "description": "Game designer"},
            {"slug": "performance-benchmarker", "division": "performance", "description": "Performance"},
            {"slug": "test-automation-engineer", "division": "quality", "description": "Test automation"},
        ]
        
        # Atlas
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(result, ("sre-site-reliability-engineer", "multi-agent-systems-architect"))
        
        # Rei-da-laje
        result = select_specialists("rei-da-laje", "pipa combate e performance benchmark", candidates, max_agents=2)
        self.assertEqual(result, ("game-designer", "performance-benchmarker"))
        
        # Lanchonete-do-guru
        result = select_specialists("lanchonete-do-guru", "backend api e testes automatizados", candidates, max_agents=2)
        self.assertEqual(result, ("backend-architect", "test-automation-engineer"))

    def test_no_hallucinated_slugs_ever_selected(self):
        """No invented/hallucinated slugs are ever selected; only candidates in pool."""
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
        ]
        
        # Objective mentions something not in catalog
        result = select_specialists("atlas", "kubernetes devops engineer docker", candidates, max_agents=2)
        # Should not select anything since no keywords match
        self.assertEqual(result, ())
        
        # Even if objective matches, only candidates in pool can be selected
        result = select_specialists("atlas", "monitoramento de serviços", candidates, max_agents=2)
        self.assertEqual(result, ("sre-site-reliability-engineer",))
        # multi-agent-systems-architect not selected because objective doesn't match its keywords

    def test_at_most_two_agents_total_across_logical_roles(self):
        """At most 2 total agents selected, respecting max_agents and logical role deduplication."""
        candidates = [
            {"slug": "sre-site-reliability-engineer", "division": "platform", "description": "SRE"},
            {"slug": "sre", "division": "engineering", "description": "SRE legacy"},
            {"slug": "multi-agent-systems-architect", "division": "architecture", "description": "Multi-agent"},
            {"slug": "game-designer", "division": "gameplay", "description": "Game designer"},
        ]
        
        # Objective matches both atlas roles
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, ("sre-site-reliability-engineer", "multi-agent-systems-architect"))
        
        # With max_agents=1, only highest priority
        result = select_specialists("atlas", "monitoramento de serviços e arquitetura de agentes", candidates, max_agents=1)
        self.assertEqual(result, ("sre-site-reliability-engineer",))


if __name__ == "__main__":
    unittest.main()