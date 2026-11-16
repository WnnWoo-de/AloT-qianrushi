(function () {
    const namespace = window.API_CONFIG.CACHE_NAMESPACE
    const entityNames = ['system', 'robots', 'tasks', 'events', 'map', 'statistics', 'ui']

    function key(name) {
        return namespace + '.' + name
    }

    function read(name) {
        try {
            const raw = localStorage.getItem(key(name))
            return raw ? JSON.parse(raw) : null
        } catch (_) {
            return null
        }
    }

    function write(name, value) {
        if (value === undefined || value === null) return
        try {
            localStorage.setItem(key(name), JSON.stringify(value))
        } catch (_) {}
    }

    function seed(defaultState) {
        entityNames.forEach(name => {
            if (read(name) === null && defaultState[name] !== undefined) {
                write(name, defaultState[name])
            }
        })
    }

    function readAll(defaultState = {}) {
        return entityNames.reduce((state, name) => {
            const cached = read(name)
            state[name] = cached === null ? defaultState[name] : cached
            return state
        }, {})
    }

    function writeMany(partialState) {
        Object.keys(partialState || {}).forEach(name => {
            if (entityNames.includes(name)) write(name, partialState[name])
        })
    }

    window.CloudStateStore = { read, write, seed, readAll, writeMany }
})()
