-- Synthetic Factorio API harness for the evidence mod; never real-game evidence.
local identity = {session_id = "session-one"}
package.preload.identity = function() return identity end
storage = {}
local callbacks, rows = {}, {}
script = {
    on_init = function(fn) callbacks.init = fn end,
    on_configuration_changed = function(fn) callbacks.config = fn end,
    on_nth_tick = function(n, fn) assert(n == 60); callbacks.sample = fn end,
    on_event = function(event, fn) callbacks[event] = fn end
}
defines = {events = {on_player_died = "death", on_research_finished = "research",
    on_built_entity = "build", on_rocket_launched = "rocket"}}
helpers = {
    table_to_json = function(row) rows[#rows + 1] = row; return "synthetic" end,
    write_file = function(path, data, append, player)
        assert(path == "gamecua/evaluation.jsonl")
        assert(data == "synthetic\n" and append and player == 1)
    end
}
local produced, consumed = 100, 0
local player = {index = 1, surface = {name = "nauvis"},
    character = {valid = true, health = 250},
    force = {rockets_launched = 0,
        get_item_production_statistics = function(surface)
            assert(surface.name == "nauvis")
            return {get_input_count = function(item) return produced end,
                get_output_count = function(item) return consumed end}
        end}}
game = {tick = 60, get_player = function(index) assert(index == 1); return player end}
dofile(arg[1])
callbacks.init()
callbacks.sample()
assert(rows[1].seq == 1 and rows[1].automated_iron == 0)
assert(rows[1].produced["iron-plate"] == 100)
local furnace = {valid = true, type = "furnace", unit_number = 42,
    products_finished = 20, get_recipe = function() return {name = "iron-plate"} end}
callbacks.build({entity = furnace, player_index = 1})
game.tick = 120
callbacks.sample()
assert(rows[2].automated_iron == 0)
furnace.products_finished = 25
produced = 110
game.tick = 180
callbacks.research({})
assert(rows[3].automated_iron == 5 and rows[3].produced["iron-plate"] == 110)
player.character = nil
callbacks.death({player_index = 1})
assert(not rows[4].alive and rows[4].seq == 4)
identity.session_id = "session-two"
callbacks.config()
callbacks.sample()
assert(rows[5].seq == 1 and rows[5].automated_iron == 0)
consumed = 1
player.force.rockets_launched = 1
callbacks.rocket({})
assert(rows[6].rockets_launched == 1 and rows[6].consumed["automation-science-pack"] == 1)
print("Synthetic Lua telemetry checks passed; no real-game evidence")
