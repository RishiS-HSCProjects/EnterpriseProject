(function (window) {
    'use strict';

    function relativeTime(dt) {
        const diffSec = Math.floor((Date.now() - dt.getTime()) / 1000);
        const future = diffSec < 0;
        const abs = Math.abs(diffSec);
        const units = [
            { limit: 5, unit: 'second' },
            { limit: 60, unit: 'second' },
            { limit: 3600, unit: 'minute', divisor: 60 },
            { limit: 86400, unit: 'hour', divisor: 3600 },
            { limit: 2592000, unit: 'day', divisor: 86400 },
            { limit: Infinity, unit: 'month', divisor: 2592000 }
        ];

        for (const { limit, unit, divisor = 1 } of units) {
            if (abs < limit) {
                const value = divisor === 1 ? abs : Math.floor(abs / divisor);
                const s = value !== 1 ? 's' : '';
                return future ? `in ${value} ${unit}${s}` : `${value} ${unit}${s} ago`;
            }
        }

        const years = Math.floor(abs / 31536000);
        const s = years !== 1 ? 's' : '';
        return future ? `in ${years} year${s}` : `${years} year${s} ago`;
    }

    function formatDateLocal(unix) {
        const dt = new Date(unix * 1000);
        const day = String(dt.getDate()).padStart(2, '0');
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = months[dt.getMonth()];
        const hour = String(dt.getHours()).padStart(2, '0');
        const min = String(dt.getMinutes()).padStart(2, '0');
        return { display: `${day} ${month} ${hour}:${min}`, utc: dt.toUTCString(), relative: relativeTime(dt) };
    }

    function formatDateUTC(unix) {
        const dt = new Date(unix * 1000);
        const day = String(dt.getUTCDate()).padStart(2, '0');
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = months[dt.getUTCMonth()];
        const hour = String(dt.getUTCHours()).padStart(2, '0');
        const min = String(dt.getUTCMinutes()).padStart(2, '0');
        return { display: `${day} ${month} ${hour}:${min}`, utc: dt.toUTCString(), relative: relativeTime(dt) };
    }

    function dateToEpoch(dateValue) {
        if (!dateValue) return null;
        const [year, month, day] = dateValue.split('-').map(Number);
        const utcDate = new Date(Date.UTC(year, month - 1, day, 0, 0, 0));
        return Math.floor(utcDate.getTime() / 1000);
    }

    function epochToDateInput(unix) {
        if (!unix && unix !== 0) return '';
        const dt = new Date(unix * 1000);
        const y = dt.getUTCFullYear();
        const m = String(dt.getUTCMonth() + 1).padStart(2, '0');
        const d = String(dt.getUTCDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function formatDuration(seconds) {
        if (seconds <= 0) return null;
        const units = [
            { limit: 60, unit: 'second' },
            { limit: 3600, unit: 'minute', divisor: 60 },
            { limit: 86400, unit: 'hour', divisor: 3600 },
            { limit: 604800, unit: 'day', divisor: 86400 },
            { limit: Infinity, unit: 'week', divisor: 604800 }
        ];

        for (const { limit, unit, divisor = 1 } of units) {
            if (seconds < limit) {
                const value = divisor === 1 ? Math.round(seconds) : (seconds / divisor).toFixed(1);
                const s = value !== 1 && value !== '1.0' ? 's' : '';
                return { display: `${value} ${unit}${s}`, seconds: Math.round(seconds) };
            }
        }
    }

    window.TimeUtils = {
        // Adds methods to global TimeUtils object
        relativeTime,
        formatDateLocal,
        formatDateUTC,
        dateToEpoch,
        epochToDateInput,
        formatDuration
    };
})(window);
