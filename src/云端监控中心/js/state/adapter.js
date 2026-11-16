(function () {
    function clone(value) {
        return value === undefined ? undefined : JSON.parse(JSON.stringify(value))
    }

    function asArray(value) {
        return Array.isArray(value) ? value : []
    }

    function setDataset(page, index, value) {
        const component = page && page.componentList && page.componentList[index]
        if (!component || !component.option) return
        component.option.dataset = clone(value)
    }

    function applyUi(ui) {
        if (!ui || typeof ui !== 'object') return

        const p1 = ui.page1 || {}
        setDataset(page1, 6, asArray(p1.elder_alerts))
        setDataset(page1, 7, asArray(p1.robot_status))
        setDataset(page1, 10, asArray(p1.device_status))
        if (p1.today_alerts !== undefined) setDataset(page1, 19, p1.today_alerts)
        if (page1.componentList[25]?.option?.dataset) {
            page1.componentList[25].option.dataset.values = clone(asArray(p1.word_cloud))
        }
        if (p1.daily_growth_rate !== undefined) setDataset(page1, 26, p1.daily_growth_rate)
        if (p1.daily_growth_value !== undefined) setDataset(page1, 27, p1.daily_growth_value)
        if (p1.current_event !== undefined) {
            const eventGroup = page1.componentList[28]?.groupList
            const event = p1.current_event
            if (eventGroup?.[1]?.option) {
                if (event && typeof event === 'object') {
                    eventGroup[1].option.dataset = [event.location, event.type].filter(Boolean).join('      ')
                } else {
                    eventGroup[1].option.dataset = String(event || '')
                }
            }
            if (eventGroup?.[2]?.option) {
                eventGroup[2].option.dataset = event && typeof event === 'object' ? (event.image || '') : ''
            }
        }

        const p2 = ui.page2 || {}
        if (p2.today_alerts !== undefined) setDataset(page2, 2, p2.today_alerts)
        if (p2.month_alerts !== undefined) setDataset(page2, 4, p2.month_alerts)
        if (p2.daily_growth_value !== undefined) setDataset(page2, 12, p2.daily_growth_value)
        if (p2.monthly_growth_value !== undefined) setDataset(page2, 13, p2.monthly_growth_value)
        if (p2.daily_growth_rate !== undefined) setDataset(page2, 14, p2.daily_growth_rate)
        if (p2.monthly_growth_rate !== undefined) setDataset(page2, 15, p2.monthly_growth_rate)
        if (page2.componentList[16]?.option && p2.alert_comparison) {
            page2.componentList[16].option.dataset = clone(p2.alert_comparison)
        }
        setDataset(page2, 17, asArray(p2.call_content_table))
        if (page2.componentList[22]?.option?.dataset) {
            page2.componentList[22].option.dataset.values = clone(asArray(p2.hourly_calls))
        }
        setDataset(page2, 24, asArray(p2.call_summary))
        setDataset(page2, 26, asArray(p2.elder_alerts))

        const p4 = ui.page4 || {}
        setDataset(page4, 4, asArray(p4.robot_status))
        setDataset(page4, 8, asArray(p4.device_status))
        setDataset(page4, 10, asArray(p4.device_summary))
        if (page4.componentList[11]?.option?.dataset) {
            page4.componentList[11].option.dataset.values = clone(asArray(p4.alert_chart))
        }

        const p5 = ui.page5 || {}
        if (page5.componentList[4]?.option?.dataset?.dataSource) {
            page5.componentList[4].option.dataset.dataSource.data = clone(asArray(p5.satisfaction))
        }
        setDataset(page5, 5, asArray(p5.todos))
        if (page5.componentList[7]?.option) {
            page5.componentList[7].option.dataset = { messages: clone(asArray(p5.suggestions)) }
        }
    }

    function replaceOption(target, source) {
        if (!source || typeof source !== 'object') return
        Object.keys(target).forEach(key => delete target[key])
        Object.assign(target, clone(source))
    }

    function applyStatistics(statistics) {
        if (!statistics || typeof statistics !== 'object') return
        if (statistics.hourly_call_comparison) replaceOption(page2LineChart1.option, statistics.hourly_call_comparison)
        if (statistics.call_content) replaceOption(page2PieChart1.option, statistics.call_content)
        if (statistics.monthly_calls) replaceOption(page2BarChart1.option, statistics.monthly_calls)
        if (statistics.device_alerts) replaceOption(page4BarChart1.option, statistics.device_alerts)
    }

    function applyState(state) {
        if (!state) return
        applyStatistics(state.statistics)
        applyUi(state.ui)
    }

    function refreshVisiblePage() {
        if (typeof currentPageId === 'undefined' || !currentPageId) return
        if (typeof pageMap === 'undefined' || !pageMap[currentPageId]) return
        renderPage(pageMap[currentPageId])
        handleResize()
    }

    window.CloudStateAdapter = { applyState, refreshVisiblePage }
})()
