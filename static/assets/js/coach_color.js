// 教練代表色：調色盤 + 自動建議（跟現有教練差異最大的顏色）+ 太接近其他教練時提醒。
// 新增使用者頁與使用者列表的編輯彈窗共用。色差算法與後端 utils/colors.py 相同（CIELAB ΔE76）。

const COACH_COLOR_SIMILAR_THRESHOLD = 20;  // ΔE 低於此值視為「很接近」

function coachColorHexToLab(hex) {
    const h = hex.replace('#', '');
    const lin = c => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    const [r, g, b] = [0, 2, 4].map(i => lin(parseInt(h.substr(i, 2), 16) / 255));
    const x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
    const y = r * 0.2126 + g * 0.7152 + b * 0.0722;
    const z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
    const f = t => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    const [fx, fy, fz] = [f(x), f(y), f(z)];
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

function coachColorDistance(a, b) {
    const la = coachColorHexToLab(a), lb = coachColorHexToLab(b);
    return Math.sqrt(la.reduce((sum, v, i) => sum + (v - lb[i]) ** 2, 0));
}

function isValidCoachColor(value) {
    return /^#[0-9a-fA-F]{6}$/.test(value || '');
}

async function fetchSuggestedCoachColor() {
    const res = await authFetch('/api/users/coaches/suggest-color');
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '無法取得建議顏色');
    return data.color;
}

async function fetchCoachColors() {
    const res = await authFetch('/api/users/coaches');
    const data = await res.json();
    return Array.isArray(data) ? data : [];
}

// 綁定調色盤：選到跟其他教練（排除 excludeId 自己）很接近的顏色時，在 hintEl 顯示提醒。
// 回傳 refresh()，換了編輯對象或新增完一位教練後呼叫，重新抓教練顏色。
function bindCoachColorPicker(inputEl, hintEl, getExcludeId) {
    let coaches = [];

    function check() {
        const value = inputEl.value;
        const excludeId = getExcludeId ? getExcludeId() : null;
        const close = coaches
            .filter(c => c.id !== excludeId && isValidCoachColor(c.color))
            .filter(c => coachColorDistance(value, c.color) < COACH_COLOR_SIMILAR_THRESHOLD)
            .map(c => c.display_name);
        hintEl.textContent = close.length ? `跟 ${close.join('、')} 的顏色很接近，行事曆上可能不好分辨` : '';
        hintEl.classList.toggle('hidden', close.length === 0);
    }

    inputEl.addEventListener('input', check);
    return async function refresh() {
        try { coaches = await fetchCoachColors(); } catch (e) { coaches = []; }
        check();
    };
}
