"""Read-only Factorio 2.0/2.1 telemetry; only this mod's own storage is mutated."""

CONTROL = r"""
-- Evaluator-only sampler of native production, furnace output, science use and character state.
local identity = require("identity")
local items = {"iron-ore", "iron-plate", "copper-plate", "iron-gear-wheel"}

-- Reset this mod's counters once per episode session.
local function initialize()
    if storage.session_id ~= identity.session_id then
        storage.session_id = identity.session_id
        storage.seq = 0
        storage.furnaces = {}
        storage.automated_iron = 0
    end
end

-- Append one native sample to the private evidence stream.
local function sample()
    initialize()
    local player = game.get_player(1)
    if not player then return end
    local force = player.force
    for unit, record in pairs(storage.furnaces) do
        local entity = record.entity
        if entity.valid then
            local count = entity.products_finished
            local recipe = entity.get_recipe()
            if recipe and recipe.name == "iron-plate" and count > record.count then
                storage.automated_iron = storage.automated_iron + count - record.count
            end
            record.count = count
        else
            storage.furnaces[unit] = nil
        end
    end
    local stats = force.get_item_production_statistics(player.surface)
    local produced = {}
    for _, item in ipairs(items) do
        produced[item] = stats.get_input_count(item)
    end
    storage.seq = storage.seq + 1
    local row = {
        schema_version = 2,
        kind = "sample",
        session_id = identity.session_id,
        seq = storage.seq,
        tick = game.tick,
        alive = player.character ~= nil and player.character.valid
            and player.character.health > 0,
        produced = produced,
        automated_iron = storage.automated_iron,
        consumed = {
            ["automation-science-pack"] = stats.get_output_count("automation-science-pack")
        },
        rockets_launched = force.rockets_launched
    }
    helpers.write_file("gamecua/evaluation.jsonl",
        helpers.table_to_json(row) .. "\n", true, player.index)
end

script.on_init(initialize)
script.on_configuration_changed(initialize)
script.on_nth_tick(60, sample)
script.on_event(defines.events.on_player_died, sample)
script.on_event(defines.events.on_research_finished, sample)
script.on_event(defines.events.on_rocket_launched, sample)
-- Track furnaces the player builds so only their iron output counts as automation.
script.on_event(defines.events.on_built_entity, function(event)
    initialize()
    local entity = event.entity
    if event.player_index == 1 and entity and entity.valid
        and entity.type == "furnace" and entity.unit_number then
        storage.furnaces[entity.unit_number] = {
            entity = entity, count = entity.products_finished
        }
    end
end)
"""
