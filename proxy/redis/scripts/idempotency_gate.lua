---@diagnostic disable: undefined-global

local key = KEYS[1]
local ttl_seconds = tonumber(ARGV[2])
local fingerprint = ARGV[1]
local hash = redis.call('HGET', key, 'hash')

if hash == nil then
    redis.call('EXPIRE', key, ttl_seconds, 'NX') -- set expiry only when key has no existing exp
    redis.call("HSET", key, 'hash', fingerprint, 'state', 'IN_PROGRESS')
    return 'EXECUTING'
elseif hash == ARGV[1] then
    local state = redis.call('HGET', key, 'state')

    if state == 'IN_PROGRESS' then
        return 'REJECT' --reject client request
    elseif state == 'COMPLETED' then
        return 'REPLAY'
    end
else
    return 'CONFLICT'
end
