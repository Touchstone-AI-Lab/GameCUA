local G = GLOBAL
local assert, pairs, math = G.assert, G.pairs, G.math
local json = G.require("json")
local config_file = assert(G.io.open(MODROOT .. "observer.json", "r"))
local config = json.decode(config_file:read("*a"))
config_file:close()

AddSimPostInit(function(player)
    if not player then return end
    local sequence = 0
    local gathered, crafted, built, eaten = {}, {}, {}, {}
    local active = false
    local function count(items, item)
        if item and item.prefab then
            local stack = item.components.stackable
            items[item.prefab] = (items[item.prefab] or 0) + (stack and stack:StackSize() or 1)
        end
    end
    local function emit(kind, extra)
        if not active then return end
        local world = G.GetWorld()
        local clock = G.GetClock()
        if not world or not clock then return end
        local inventory = {}
        local inv = player.components.inventory
        for _, item in pairs(inv.itemslots) do count(inventory, item) end
        for _, item in pairs(inv.equipslots) do count(inventory, item) end
        count(inventory, inv.activeitem)
        local overflow = inv.overflow and inv.overflow.components.container
        if overflow then
            for _, item in pairs(overflow.slots) do count(inventory, item) end
        end
        for name, amount in pairs(inventory) do
            gathered[name] = math.max(gathered[name] or 0, amount)
        end
        sequence = sequence + 1
        local row = {
            schema_version = 1, episode_id = config.episode_id,
            snapshot_sha256 = config.snapshot_sha256,
            world_seed = world.meta.seed, character = player.prefab,
            sequence = sequence, kind = kind, age = player.components.age:GetAge(),
            cycles = clock.numcycles, phase = clock.phase,
            health = player.components.health.currenthealth,
            inventory = inventory, gathered = gathered, crafted = crafted,
            built = built, eaten = eaten,
        }
        if extra then row.detail = extra end
        G.print("GAMECUA_OBSERVER " .. json.encode(row))
    end
    local function increment(target, item)
        if item and item.prefab then target[item.prefab] = (target[item.prefab] or 0) + 1 end
    end
    player:ListenForEvent("builditem", function(_, data)
        if active then increment(crafted, data and data.item) emit("craft") end
    end)
    player:ListenForEvent("buildstructure", function(_, data)
        if active then increment(built, data and data.item) emit("build") end
    end)
    player:ListenForEvent("oneat", function(_, data)
        if active then increment(eaten, data and data.food) emit("eat") end
    end)
    player:ListenForEvent("death", function(_, data)
        emit("death", {cause = data and data.cause or "unknown"})
    end)
    player:ListenForEvent("itemget", function() emit("inventory") end)
    player:DoTaskInTime(0, function()
        active = true
        emit("initial")
        player:DoPeriodicTask(0.5, function() emit("sample") end)
    end)
end)
