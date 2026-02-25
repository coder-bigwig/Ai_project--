const TOKEN_COOKIE_NAME = 'training_jhub_token';
const TOKEN_COOKIE_MAX_AGE_SECONDS = 43200;
const JUPYTER_COOKIE_PATH = '/jupyter/';
const DEV_JUPYTER_PORT = '8003';

function _normalizeBaseUrl(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    return raw.replace(/\/+$/, '');
}

function _isLikelyLocalDevServer() {
    const host = String(window.location.hostname || '').toLowerCase();
    const port = String(window.location.port || '');
    const isLocalHost = host === 'localhost' || host === '127.0.0.1';
    // CRA dev server typically runs on 3000+.
    const isDevPort = /^3\d{3}$/.test(port);
    return isLocalHost && isDevPort;
}

function _resolveJupyterUrlForCurrentEnv(rawUrl) {
    const parsedUrl = new URL(rawUrl, window.location.origin);
    const isRelativeJupyterPath =
        parsedUrl.origin === window.location.origin && parsedUrl.pathname.startsWith('/jupyter/');

    if (!isRelativeJupyterPath) {
        return parsedUrl.toString();
    }

    const configuredPublicUrl = _normalizeBaseUrl(process.env.REACT_APP_JUPYTERHUB_URL);
    if (configuredPublicUrl) {
        return `${configuredPublicUrl}${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    if (_isLikelyLocalDevServer()) {
        const devHubOrigin = `${window.location.protocol}//${window.location.hostname}:${DEV_JUPYTER_PORT}`;
        return `${devHubOrigin}${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    return parsedUrl.toString();
}

export function persistJupyterTokenFromUrl(rawUrl) {
    if (!rawUrl) {
        return rawUrl;
    }

    try {
        const resolvedUrl = _resolveJupyterUrlForCurrentEnv(rawUrl);
        const parsedUrl = new URL(resolvedUrl, window.location.origin);
        const token = parsedUrl.searchParams.get('token');

        if (!token) {
            return resolvedUrl;
        }

        document.cookie = `${TOKEN_COOKIE_NAME}=${encodeURIComponent(token)}; Path=${JUPYTER_COOKIE_PATH}; Max-Age=${TOKEN_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
        return resolvedUrl;
    } catch (error) {
        // Ignore parsing errors and keep the original URL flow.
        return rawUrl;
    }
}

