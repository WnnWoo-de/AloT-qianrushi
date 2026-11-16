(function () {
    let socket = null

    function upsertById(list, item, keys) {
        const source = Array.isArray(list) ? list.slice() : []
        const key = keys.find(name => item && item[name] !== undefined)
        if (!key) return source
        const index = source.findIndex(entry => entry && entry[key] === item[key])
        if (index >= 0) source[index] = Object.assign({}, source[index], item)
        else source.unshift(item)
        return source
    }

    async function syncRestState() {
        if (!ApiClient.hasApiEndpoint()) return false

        const requests = {
            system: ApiClient.getSystemStatus(),
            robots: ApiClient.getRobots(),
            tasks: ApiClient.getTasks(),
            events: ApiClient.getEvents(),
            map: ApiClient.getMap(),
            statistics: ApiClient.getStatistics(),
            ui: ApiClient.getUi()
        }
        const entries = Object.entries(requests)
        const settled = await Promise.allSettled(entries.map(([, promise]) => promise))
        const nextState = {}

        settled.forEach((result, index) => {
            if (result.status === 'fulfilled' && result.value !== undefined && result.value !== null) {
                nextState[entries[index][0]] = result.value
            }
        })

        if (!Object.keys(nextState).length) return false
        CloudStateStore.writeMany(nextState)
        CloudStateAdapter.applyState(nextState)
        return true
    }

    async function restore() {
        const defaults = CloudBootstrapData.createBootstrapState()
        CloudStateStore.seed(defaults)
        const cached = CloudStateStore.readAll(defaults)
        CloudStateAdapter.applyState(cached)
        try {
            await syncRestState()
        } catch (_) {}
    }

    function handleRealtimeMessage(message) {
        const mapping = {
            robot_update: 'robots',
            task_update: 'tasks',
            event_update: 'events',
            system_update: 'system'
        }
        const entity = mapping[message.type]
        if (!entity) return

        let value = message.data
        if (entity === 'robots' && !Array.isArray(value)) {
            value = upsertById(CloudStateStore.read('robots'), value, ['robot_id', 'id'])
        } else if (entity === 'tasks' && !Array.isArray(value)) {
            value = upsertById(CloudStateStore.read('tasks'), value, ['task_id', 'id'])
        } else if (entity === 'events' && !Array.isArray(value)) {
            value = upsertById(CloudStateStore.read('events'), value, ['event_id', 'id'])
        }

        CloudStateStore.write(entity, value)
    }

    function startNetwork() {
        syncRestState().then(updated => {
            if (updated) CloudStateAdapter.refreshVisiblePage()
        }).catch(() => {})
        if (ApiClient.hasWsEndpoint()) {
            socket = ApiClient.connectMonitor(handleRealtimeMessage)
        }
    }

    function stopNetwork() {
        if (socket) socket.close()
        socket = null
    }

    window.CloudClientRuntime = { restore, startNetwork, stopNetwork }
})()
