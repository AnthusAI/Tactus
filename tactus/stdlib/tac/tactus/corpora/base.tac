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

local function normalize_corpus_config(config, defaults)
  local merged = merge_defaults(defaults, config or {})
  if merged.root ~= nil and merged.corpus_root == nil then
    merged.corpus_root = merged.root
    merged.root = nil
  end
  return merged
end

local function wrap_corpus(defaults)
  local function constructor(config)
    return _tactus_internal_corpus(normalize_corpus_config(config, defaults))
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
  wrap_corpus = wrap_corpus,
}
