-- Message History Transforms Demo
-- Demonstrates MessageHistory transforms like reset, head/tail, rewind, and token slicing

Procedure {
    output = {
        system_reset_count = field.number{required = true},
        head_count = field.number{required = true},
        tail_count = field.number{required = true},
        tail_tokens_count = field.number{required = true},
        rewind_count = field.number{required = true},
        rewind_to_count = field.number{required = true},
        keep_tail_count = field.number{required = true},
        keep_head_count = field.number{required = true},
        has_message_ids = field.boolean{required = true}
    },
    function(input)
        local function count_messages(messages)
            local count = 0
            for _ in python.iter(messages) do
                count = count + 1
            end
            return count
        end

        local function all_have_ids(messages)
            for msg in python.iter(messages) do
                if msg.id == nil then
                    return false
                end
            end
            return true
        end

        local function seed_history()
            MessageHistory.clear()
            MessageHistory.inject_system("System A")
            MessageHistory.inject_system("System B")
            MessageHistory.append({role = "user", content = "aaaa"})
            MessageHistory.append({role = "assistant", content = "bbbb"})
            MessageHistory.append({role = "user", content = "cccc"})
            local checkpoint_id = MessageHistory.checkpoint("mid")
            MessageHistory.append({role = "assistant", content = "dddd"})
            MessageHistory.append({role = "user", content = "eeee"})
            return checkpoint_id
        end

        seed_history()
        local head_count = count_messages(MessageHistory.head(3))
        local tail_count = count_messages(MessageHistory.tail(2))
        local tail_tokens_count = count_messages(MessageHistory.tail_tokens(2))
        local has_message_ids = all_have_ids(MessageHistory.get())

        MessageHistory.reset({keep = "system_prefix"})
        local system_reset_count = count_messages(MessageHistory.get())

        seed_history()
        MessageHistory.rewind(2)
        local rewind_count = count_messages(MessageHistory.get())

        local checkpoint_id = seed_history()
        MessageHistory.rewind_to(checkpoint_id)
        local rewind_to_count = count_messages(MessageHistory.get())

        seed_history()
        MessageHistory.keep_tail(3)
        local keep_tail_count = count_messages(MessageHistory.get())

        seed_history()
        MessageHistory.keep_head(4)
        local keep_head_count = count_messages(MessageHistory.get())

        return {
            system_reset_count = system_reset_count,
            head_count = head_count,
            tail_count = tail_count,
            tail_tokens_count = tail_tokens_count,
            rewind_count = rewind_count,
            rewind_to_count = rewind_to_count,
            keep_tail_count = keep_tail_count,
            keep_head_count = keep_head_count,
            has_message_ids = has_message_ids
        }
    end
}
