-- Example: missing dependency (blocked execution).
-- Run:
--   tactus examples/99-task-deps-blocked.tac extract

Task "extract" {
  depends_on = { "load" },
  entry = function()
    return { status = "extracted" }
  end
}

return { status = "ready" }
