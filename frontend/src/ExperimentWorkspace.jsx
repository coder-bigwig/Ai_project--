import React, { useEffect, useRef, useState } from 'react';
import Split from 'react-split';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { persistJupyterTokenFromUrl } from './jupyterAuth';
import './ExperimentWorkspace.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

function isPdfDocument(doc) {
    const fileName = String(doc?.fileName || '').toLowerCase();
    const fileType = String(doc?.fileType || '').toLowerCase();
    return fileName.endsWith('.pdf') || fileType === 'application/pdf';
}

function isPptxDocument(doc) {
    const fileName = String(doc?.fileName || '').toLowerCase();
    const fileType = String(doc?.fileType || '').toLowerCase();
    return (
        fileName.endsWith('.pptx')
        || fileType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    );
}

function isPptDocument(doc) {
    const fileName = String(doc?.fileName || '').toLowerCase();
    const fileType = String(doc?.fileType || '').toLowerCase();
    return fileName.endsWith('.ppt') || fileType === 'application/vnd.ms-powerpoint';
}

function isMarkdownDocument(doc) {
    const fileName = String(doc?.fileName || '').toLowerCase();
    const fileType = String(doc?.fileType || '').toLowerCase();
    return (
        fileName.endsWith('.md')
        || fileName.endsWith('.markdown')
        || fileType === 'text/markdown'
        || fileType === 'text/x-markdown'
    );
}

function isTextDocument(doc) {
    const fileName = String(doc?.fileName || '').toLowerCase();
    const fileType = String(doc?.fileType || '').toLowerCase();
    if (isMarkdownDocument(doc)) return true;
    if (fileName.endsWith('.txt') || fileName.endsWith('.csv') || fileName.endsWith('.json')) return true;
    if (fileType === 'application/json') return true;
    return fileType.startsWith('text/');
}

function getDocPreviewPriority(doc) {
    if (isPdfDocument(doc)) return 0;
    if (isPptxDocument(doc)) return 1;
    if (isPptDocument(doc)) return 2;
    if (isTextDocument(doc)) return 3;
    return 4;
}

function getFileExtension(fileName) {
    const normalized = String(fileName || '').trim();
    const match = normalized.match(/\.[^.]+$/);
    return match ? match[0].toLowerCase() : '';
}

function getAttachmentDisplayName(fileName, experimentTitle, index) {
    const extension = getFileExtension(fileName);
    const normalizedTitle = String(experimentTitle || '').trim();
    const baseName = normalizedTitle || `实验文档${index + 1}`;

    if (extension === '.pdf') {
        return `${baseName}（预览）${extension}`;
    }
    if (extension === '.doc' || extension === '.docx') {
        return `${baseName}（附件）${extension}`;
    }
    return extension ? `${baseName}${extension}` : baseName;
}

function getAbsoluteUri(uri) {
    if (!uri) return uri;
    if (uri.startsWith('http://') || uri.startsWith('https://')) return uri;
    return `${window.location.origin}${uri}`;
}

function UnsupportedPreview({ uri, fileName }) {
    return (
        <div className="no-preview">
            <div className="file-icon">📄</div>
            <h3>{fileName}</h3>
            <p>该文件暂不支持在线预览，请下载后查看。</p>
            <a href={uri} className="download-btn" download>
                下载查看
            </a>
        </div>
    );
}

function PptxPreview({ uri, fileName }) {
    const hostRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let cancelled = false;
        const hostElement = hostRef.current;

        const renderPptx = async () => {
            setLoading(true);
            setError('');

            if (!hostElement) return;
            hostElement.innerHTML = '';

            try {
                const [{ init }, response] = await Promise.all([
                    import('pptx-preview'),
                    axios.get(uri, { responseType: 'arraybuffer' })
                ]);

                if (cancelled) return;

                const width = Math.max(hostElement.clientWidth - 24, 640);
                const height = Math.max(Math.round(width * 9 / 16), 360);
                const previewer = init(hostElement, { width, height });
                await previewer.preview(response.data);
            } catch (previewError) {
                console.error('Failed to preview pptx:', previewError);
                if (!cancelled) {
                    setError('PPTX 预览失败，请下载后查看。');
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        renderPptx();
        return () => {
            cancelled = true;
            if (hostElement) {
                hostElement.innerHTML = '';
            }
        };
    }, [uri]);

    if (error) {
        return (
            <div className="no-preview">
                <div className="file-icon">📊</div>
                <h3>{fileName}</h3>
                <p>{error}</p>
                <a href={uri} className="download-btn" download>
                    下载查看
                </a>
            </div>
        );
    }

    return (
        <div className="ppt-preview-wrapper">
            {loading ? <div className="loading-pane">正在加载课件...</div> : null}
            <div ref={hostRef} className="ppt-preview-host" style={{ display: loading ? 'none' : 'block' }} />
        </div>
    );
}

function OfficePptPreview({ uri, fileName }) {
    const absoluteUri = getAbsoluteUri(uri);
    const officeEmbedUri = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(absoluteUri)}`;

    return (
        <div className="ppt-preview-wrapper">
            <iframe src={officeEmbedUri} title={fileName} className="ppt-office-iframe" frameBorder="0" />
            <div className="ppt-preview-tip">
                若预览失败，请直接下载查看。
                <a href={uri} download>下载文件</a>
            </div>
        </div>
    );
}

function TextDocumentPreview({ uri, fileName }) {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [content, setContent] = useState('');

    useEffect(() => {
        let cancelled = false;

        const loadText = async () => {
            setLoading(true);
            setError('');
            setContent('');
            try {
                const response = await axios.get(uri, { responseType: 'text' });
                if (cancelled) return;
                const text = typeof response.data === 'string'
                    ? response.data
                    : JSON.stringify(response.data, null, 2);
                setContent(text || '');
            } catch (loadError) {
                console.error('Failed to load text preview:', loadError);
                if (!cancelled) {
                    setError('文本预览加载失败，请下载后查看。');
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        loadText();
        return () => {
            cancelled = true;
        };
    }, [uri]);

    if (loading) {
        return <div className="loading-pane">正在加载文档...</div>;
    }

    if (error) {
        return <UnsupportedPreview uri={uri} fileName={fileName} />;
    }

    return <pre className="workspace-text-preview">{content || '暂无内容'}</pre>;
}

function ExperimentWorkspace() {
    const { experimentId } = useParams();
    const navigate = useNavigate();
    const [experiment, setExperiment] = useState(null);
    const [docs, setDocs] = useState([]);
    const [activeDocIndex, setActiveDocIndex] = useState(0);
    const [, setStudentExp] = useState(null);
    const [jupyterUrl, setJupyterUrl] = useState('');
    const username = String(localStorage.getItem('username') || '').trim();
    const userRole = String(localStorage.getItem('userRole') || '').trim().toLowerCase();
    const isTeacherOrAdmin = userRole === 'teacher' || userRole === 'admin';

    useEffect(() => {
        if (!username) {
            alert('请先登录');
            navigate('/');
            return;
        }
        loadData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [experimentId, username]);

    const loadData = async () => {
        try {
            const expRes = await axios.get(`${API_BASE_URL}/api/experiments/${experimentId}`);
            setExperiment(expRes.data);

            const attRes = await axios.get(`${API_BASE_URL}/api/experiments/${experimentId}/attachments`);
            const fetchedAttachments = attRes.data || [];

            if (fetchedAttachments.length > 0) {
                const formattedDocs = fetchedAttachments
                    .map((att, index) => ({
                        uri: `/api/attachments/${att.id}/download`,
                        fileName: att.filename,
                        displayName: getAttachmentDisplayName(att.filename, expRes.data?.title, index),
                        fileType: att.content_type,
                    }))
                    .sort((a, b) => getDocPreviewPriority(a) - getDocPreviewPriority(b));

                setDocs(formattedDocs);
                setActiveDocIndex(0);
            } else {
                setDocs([]);
                setActiveDocIndex(0);
            }

            if (isTeacherOrAdmin) {
                const hubResp = await axios.get(
                    `${API_BASE_URL}/api/jupyterhub/auto-login-url`,
                    { params: { username, experiment_id: experimentId } }
                );
                const resolvedTeacherUrl = persistJupyterTokenFromUrl(hubResp?.data?.jupyter_url || '');
                setJupyterUrl(resolvedTeacherUrl);
                return;
            }

            const startRes = await axios.post(
                `${API_BASE_URL}/api/student-experiments/start/${experimentId}`,
                null,
                { params: { student_id: username } }
            );
            const resolvedJupyterUrl = persistJupyterTokenFromUrl(startRes.data.jupyter_url);
            setJupyterUrl(resolvedJupyterUrl);

            if (startRes.data.student_experiment_id) {
                try {
                    const detailRes = await axios.get(
                        `${API_BASE_URL}/api/student-experiments/${startRes.data.student_experiment_id}`
                    );
                    setStudentExp(detailRes.data);
                } catch (detailErr) {
                    console.warn('Failed to load student experiment detail:', detailErr);
                }
            }
        } catch (error) {
            console.error('Failed to load workspace data:', error);
            const detail = error?.response?.data?.detail;
            alert(detail ? `加载实验数据失败：${detail}` : '加载实验数据失败');
        }
    };

    const handleBackToCourseList = () => {
        if (isTeacherOrAdmin) {
            navigate('/');
            return;
        }
        navigate('/');
    };

    return (
        <div className="workspace-container">
            <div className="workspace-header">
                <button onClick={handleBackToCourseList} className="back-btn">← 返回</button>
                <h2>{experiment?.title}</h2>
                <div className="workspace-info">
                    <span>{username}</span>
                </div>
            </div>

            <Split
                className="workspace-split"
                sizes={[40, 60]}
                minSize={300}
                expandToMin={false}
                gutterSize={10}
                gutterAlign="center"
                snapOffset={30}
                dragInterval={1}
                direction="horizontal"
                cursor="col-resize"
            >
                <div className="left-pane">
                    {docs.length > 0 ? (
                        <div
                            className="doc-container"
                            style={{
                                height: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                minHeight: 0
                            }}
                        >
                            {docs.length > 1 ? (
                                <div className="doc-tabs">
                                    {docs.map((doc, index) => (
                                        <button
                                            key={doc.uri}
                                            className={`doc-tab-btn ${index === activeDocIndex ? 'active' : ''}`}
                                            onClick={() => setActiveDocIndex(index)}
                                        >
                                            {doc.displayName || doc.fileName}
                                        </button>
                                    ))}
                                </div>
                            ) : null}

                            {docs.map((doc, index) => (
                                <div
                                    key={doc.uri}
                                    style={{
                                        flex: 1,
                                        minHeight: 0,
                                        display: index === activeDocIndex ? 'block' : 'none'
                                    }}
                                >
                                    {isPdfDocument(doc) ? (
                                        <iframe
                                            src={doc.uri}
                                            title={doc.displayName || doc.fileName}
                                            style={{ width: '100%', height: '100%', border: 'none' }}
                                        />
                                    ) : isPptxDocument(doc) ? (
                                        <PptxPreview uri={doc.uri} fileName={doc.displayName || doc.fileName} />
                                    ) : isPptDocument(doc) ? (
                                        <OfficePptPreview uri={doc.uri} fileName={doc.displayName || doc.fileName} />
                                    ) : isTextDocument(doc) ? (
                                        <TextDocumentPreview uri={doc.uri} fileName={doc.displayName || doc.fileName} />
                                    ) : (
                                        <UnsupportedPreview uri={doc.uri} fileName={doc.displayName || doc.fileName} />
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="no-doc">
                            <h3>实验指导书</h3>
                            <p>本实验暂时无附件资料。</p>
                            {experiment?.description ? (
                                <div className="text-description">
                                    <h4>描述：</h4>
                                    <p>{experiment.description}</p>
                                </div>
                            ) : null}
                        </div>
                    )}
                </div>

                <div className="right-pane">
                    {jupyterUrl ? (
                        <iframe
                            src={jupyterUrl}
                            title="JupyterLab"
                            className="jupyter-iframe"
                            allow="clipboard-read; clipboard-write"
                        />
                    ) : (
                        <div className="loading-pane">正在加载实验环境...</div>
                    )}
                </div>
            </Split>
        </div>
    );
}

export default ExperimentWorkspace;
