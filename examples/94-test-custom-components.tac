--[[
Test Custom HITL Components

This example demonstrates the new Human.custom() method which allows
rendering of arbitrary custom UI components in the IDE.

Run with: tactus run examples/94-test-custom-components.tac
--]]

Procedure {
    function(input)
        print("Testing Custom HITL Components")

        -- Test 1: Image Selector Component
        print("\n=== TEST 1: IMAGE SELECTOR ===")

        -- Simulated image URLs (in real use, these would come from an image generation tool)
        local images = {
            {url = "https://picsum.photos/seed/sunset/800/450", label = "Sunset Beach"},
            {url = "https://picsum.photos/seed/mountain/800/450", label = "Mountain Vista"},
            {url = "https://picsum.photos/seed/ocean/800/450", label = "Ocean Waves"},
            {url = "https://picsum.photos/seed/forest/800/450", label = "Forest Path"}
        }

        local result = Human.custom({
            component_type = "image-selector",
            message = "Select the hero image for the landing page",
            data = {
                images = images,
                aspect_ratio = "16:9"
            },
            actions = {
                {id = "regenerate", label = "Regenerate All", style = "secondary"}
            }
        })

        print("Selection result type: " .. type(result))

        -- Check if user clicked an action button
        if type(result) == "table" and result.action == "regenerate" then
            print("User requested regeneration - would regenerate images here")
            return {
                completed = false,
                reason = "regenerate_requested"
            }
        else
            -- User selected an image
            local selected_url = result
            print("User selected image: " .. tostring(selected_url))

            -- Find which image was selected
            local selected_label = "Unknown"
            for _, img in ipairs(images) do
                if img.url == selected_url then
                    selected_label = img.label
                    break
                end
            end

            print("Selected: " .. selected_label)

            return {
                completed = true,
                selected_image_url = selected_url,
                selected_image_label = selected_label
            }
        end
    end
}
