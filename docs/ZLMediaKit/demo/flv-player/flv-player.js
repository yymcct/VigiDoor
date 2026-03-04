const streamConfig = {
    host: '192.168.1.119',
    httpPort: '80',
    app: 'live',
    stream: 'VIGIDOOR_a6540c7401ec6c79_RPI',
    vhost: '__defaultVhost__'
};

const flvUrl = `http://${streamConfig.host}:${streamConfig.httpPort}/${streamConfig.app}/${streamConfig.stream}.live.flv?vhost=${streamConfig.vhost}`;
document.getElementById('flvUrl').textContent = flvUrl;

const video = document.getElementById('videoPlayer');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const btnPlay = document.getElementById('btnPlay');
const btnStop = document.getElementById('btnStop');

let flvPlayer = null;
let reconnectTimer = null;
let reconnectCount = 0;
const maxReconnect = 3;

function setStatus(type, text) {
    const cls = {
        idle: 'bg-gray-400',
        loading: 'bg-yellow-500 animate-pulse',
        playing: 'bg-green-500 animate-pulse',
        error: 'bg-red-500'
    };
    statusDot.className = `w-3 h-3 rounded-full ${cls[type] || cls.idle}`;
    statusText.textContent = text;
}

function clearReconnect() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
}

function destroyPlayer() {
    clearReconnect();
    if (flvPlayer) {
        try {
            flvPlayer.pause();
            flvPlayer.unload();
            flvPlayer.detachMediaElement();
            flvPlayer.destroy();
        } catch (err) {
            console.warn('销毁播放器失败:', err);
        }
        flvPlayer = null;
    }

    try {
        video.pause();
        video.removeAttribute('src');
        video.srcObject = null;
        video.load();
    } catch (err) {
        console.warn('清理 video 失败:', err);
    }

    setStatus('idle', '停止中...');

    setStatus('idle', '未连接');
}

function scheduleReconnect() {
    if (reconnectCount >= maxReconnect) {
        setStatus('error', '播放失败，重连次数已达上限');
        return;
    }
    reconnectCount += 1;
    setStatus('loading', `连接中...(${reconnectCount}/${maxReconnect})`);
    reconnectTimer = setTimeout(() => {
        startPlay();
    }, 1500);
}

async function startPlay() {
    if (!window.flvjs || !flvjs.isSupported()) {
        setStatus('error', '当前浏览器不支持 FLV 播放');
        return;
    }

    destroyPlayer();

    setStatus('loading', '连接中...');

    flvPlayer = flvjs.createPlayer({
        type: 'flv',
        url: flvUrl,
        isLive: true,
        hasAudio: true,
        hasVideo: true,
        enableStashBuffer: false,
        autoCleanupSourceBuffer: true,
        autoCleanupMaxBackwardDuration: 3,
        autoCleanupMinBackwardDuration: 2,
        fixAudioTimestampGap: true,
        lazyLoad: false
    });

    flvPlayer.attachMediaElement(video);
    flvPlayer.load();

    flvPlayer.on(flvjs.Events.ERROR, (errType, errDetail) => {
        console.error('FLV 错误:', errType, errDetail);
        setStatus('error', `播放异常: ${errType}`);
        scheduleReconnect();
    });

    video.play().then(() => {
        reconnectCount = 0;
        setStatus('playing', '正在播放');
    }).catch((err) => {
        console.error('播放失败:', err);
        setStatus('error', '播放失败，正在重试');
        scheduleReconnect();
    });
}

btnPlay.addEventListener('click', startPlay);
btnStop.addEventListener('click', destroyPlayer);

window.addEventListener('load', () => {
    startPlay();
});

window.addEventListener('beforeunload', () => {
    destroyPlayer();
});
