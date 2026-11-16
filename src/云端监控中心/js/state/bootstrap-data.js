(function () {
    function clone(value) {
        return value === undefined ? undefined : JSON.parse(JSON.stringify(value))
    }

    function createBootstrapState() {
        const snapshot = window.__CLOUD_MONITOR_CACHE__
        if (snapshot && typeof snapshot === 'object') return clone(snapshot)
        return {
            system: {},
            robots: [],
            tasks: [],
            events: [],
            map: {},
            statistics: {},
            ui: {}
        }
    }

    window.CloudBootstrapData = { createBootstrapState }
})()
