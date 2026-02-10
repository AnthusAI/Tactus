-- Custom task dependencies with explicit depends_on.
-- Run:
--   tactus examples/98-task-deps-custom.tac run

Task "load" {
  entry = function()
    return { status = "loaded" }
  end
}

Task "extract" {
  depends_on = { "load" },
  entry = function()
    return { status = "extracted" }
  end
}

Task "index" {
  depends_on = { "extract" },
  entry = function()
    return { status = "indexed" }
  end
}

Task "run" {
  depends_on = { "index" },
  entry = function()
    return { status = "done" }
  end
}

return { status = "ready" }
