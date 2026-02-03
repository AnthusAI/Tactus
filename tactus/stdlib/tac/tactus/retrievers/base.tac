local function merge_defaults(defaults, config)
  local merged = {}
  if defaults then
    for key, value in pairs(defaults) do
      merged[key] = value
    end
  end
  if config then
    for key, value in pairs(config) do
      merged[key] = value
    end
  end
  return merged
end

local corpora_base = require("tactus.corpora.base")

local function wrap_retriever(defaults)
  local function constructor(config)
    local merged = merge_defaults(defaults, config or {})
    return _tactus_internal_retriever(merged)
  end
  local cls = {}
  function cls:new(config)
    return constructor(config)
  end
  return setmetatable(cls, {
    __call = function(_, config)
      return constructor(config)
    end,
  })
end

return {
  wrap_corpus = corpora_base.wrap_corpus,
  wrap_retriever = wrap_retriever,
}
