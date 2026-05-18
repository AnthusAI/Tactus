-- Web research utilities
--
-- Provides provider-backed web search and synthesis through one Tactus stdlib
-- module. Provider adapters live in Python; agents consume this facade.

local impl = require("tactus.web.impl")

return {
    providers = impl.providers,
    search = impl.search,
    synthesize = impl.synthesize,

    -- Reserved for a future async Gemini Deep Research milestone.
    deep_research_start = impl.deep_research_start,
    deep_research_status = impl.deep_research_status,
    deep_research_result = impl.deep_research_result,
}

