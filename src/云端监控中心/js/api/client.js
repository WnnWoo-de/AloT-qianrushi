(function () {
    const config = window.API_CONFIG

    function trimTrailingSlash(value) {
        return String(value || '').replace(/\/+$/, '')
    }

    function isHttpPage() {
        return window.location.protocol === 'http:' || window.location.protocol === 'https:'
    }

    function apiBase() {
        const configured = trimTrailingSlash(config.API_BASE_URL)
        return configured || (isHttpPage() ? window.location.origin : '')
    }

    function wsBase() {
        const configured = trimTrailingSlash(config.WS_BASE_URL)
        if (configured) return configured
        if (!isHttpPage()) return ''
        return (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host
    }

    function buildApiUrl(path) {
        const base = apiBase()
        const prefix = trimTrailingSlash(config.API_PREFIX)
        const suffix = String(path || '').startsWith('/') ? path : '/' + path
        return base + prefix + suffix
    }

    function buildWsUrl(path) {
        const base = wsBase()
        const suffix = String(path || '').startsWith('/') ? path : '/' + path
        return base + suffix
    }

    function hasApiEndpoint() {
        return Boolean(apiBase())
    }

    function hasWsEndpoint() {
        return Boolean(wsBase())
    }

    async function request(path, options = {}) {
        if (!hasApiEndpoint()) {
            throw new Error('SERVICE_ENDPOINT_UNAVAILABLE')
        }

        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), config.REQUEST_TIMEOUT)

        try {
            const response = await fetch(buildApiUrl(path), {
                method: options.method || 'GET',
                headers: Object.assign({ 'Content-Type': 'application/json' }, options.headers || {}),
                body: options.body === undefined ? undefined : JSON.stringify(options.body),
                signal: controller.signal
            })

            if (!response.ok) {
                throw new Error('HTTP_' + response.status)
            }

            const payload = await response.json()
            if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'code')) {
                if (payload.code !== 0) {
                    throw new Error(payload.message || 'BUSINESS_ERROR')
                }
                return payload.data
            }
            return payload
        } finally {
            clearTimeout(timeout)
        }
    }

    function connectMonitor(onMessage, onStateChange) {
        if (!hasWsEndpoint()) return null

        const socket = new WebSocket(buildWsUrl('/ws/monitor'))
        socket.addEventListener('open', () => onStateChange && onStateChange('open'))
        socket.addEventListener('close', () => onStateChange && onStateChange('closed'))
        socket.addEventListener('error', () => onStateChange && onStateChange('error'))
        socket.addEventListener('message', event => {
            try {
                const message = JSON.parse(event.data)
                if (message && message.type && Object.prototype.hasOwnProperty.call(message, 'data')) {
                    onMessage && onMessage(message)
                }
            } catch (_) {}
        })
        return socket
    }

    window.ApiClient = {
        hasApiEndpoint,
        hasWsEndpoint,
        getSystemStatus: () => request('/system/status'),
        getRobots: () => request('/robots'),
        getRobotDetail: robotId => request('/robots/' + encodeURIComponent(robotId)),
        getTasks: () => request('/tasks'),
        getCurrentTask: () => request('/tasks/current'),
        getEvents: () => request('/events'),
        getCurrentEvent: () => request('/events/current'),
        getMap: () => request('/map'),
        getStatistics: () => request('/statistics'),
        getUi: () => request('/ui'),
        connectMonitor
    }
})()
