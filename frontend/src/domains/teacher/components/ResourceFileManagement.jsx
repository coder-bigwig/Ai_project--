import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import ResourcePreviewContent from '../../../shared/resource-preview/ResourcePreviewContent';
import '../styles/ResourceFileManagement.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

const I18N = {
    fileTypeAll: '\u8bf7\u9009\u62e9\u7c7b\u578b',
    upload: '\u4e0a\u4f20\u8d44\u6599',
    uploading: '\u4e0a\u4f20\u4e2d...',
    searchPlaceholder: '\u8bf7\u8f93\u5165\u540d\u79f0',
    search: '\u641c\u7d22',
    countPrefix: '\u8d44\u6e90\u6587\u4ef6\u5171',
    tableFilename: '\u6587\u4ef6\u540d',
    tableType: '\u7c7b\u578b',
    tableCreatedAt: '\u521b\u5efa\u65f6\u95f4',
    tableAction: '\u64cd\u4f5c',
    loading: '\u52a0\u8f7d\u4e2d...',
    empty: '\u6682\u65e0\u6587\u4ef6',
    detail: '\u8be6\u60c5',
    del: '\u5220\u9664',
    detailTitle: '\u8d44\u6e90\u6587\u4ef6\u8be6\u60c5',
    close: '\u5173\u95ed',
    detailLoading: '\u8be6\u60c5\u52a0\u8f7d\u4e2d...',
    previewLoading: '\u6b63\u5728\u52a0\u8f7d\u9884\u89c8...',
    previewEmpty: '\u6682\u65e0\u53ef\u9884\u89c8\u5185\u5bb9',
    previewUnsupported: '\u5f53\u524d\u6587\u4ef6\u7c7b\u578b\u4e0d\u652f\u6301\u5728\u7ebf\u9884\u89c8\uff0c\u8bf7\u4e0b\u8f7d\u540e\u67e5\u770b\u3002',
    download: '\u4e0b\u8f7d\u6587\u4ef6',
    loadFailed: '\u52a0\u8f7d\u8d44\u6e90\u6587\u4ef6\u5931\u8d25',
    uploadSuccess: '\u8d44\u6e90\u6587\u4ef6\u4e0a\u4f20\u6210\u529f',
    uploadFailed: '\u8d44\u6e90\u6587\u4ef6\u4e0a\u4f20\u5931\u8d25',
    deleteConfirmPrefix: '\u786e\u5b9a\u5220\u9664\u6587\u4ef6',
    deleteConfirmSuffix: '\u5417\uff1f',
    deleteFailed: '\u5220\u9664\u5931\u8d25',
    detailFailed: '\u52a0\u8f7d\u8d44\u6e90\u8be6\u60c5\u5931\u8d25',
    deleted: '\u6587\u4ef6\u5df2\u5220\u9664',
};

const FILE_TYPE_OPTIONS = [
    { value: '', label: I18N.fileTypeAll },
    { value: 'pdf', label: 'pdf' },
    { value: 'doc', label: 'doc' },
    { value: 'docx', label: 'docx' },
    { value: 'xls', label: 'xls' },
    { value: 'xlsx', label: 'xlsx' },
    { value: 'md', label: 'md' },
    { value: 'txt', label: 'txt' },
];

function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
}

function buildQueryString(params) {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
        if (!key) return;
        const normalized = value === undefined || value === null ? '' : String(value).trim();
        if (!normalized) return;
        search.set(key, normalized);
    });
    return search.toString();
}

function ResourceFileManagement({
    username,
    courseId = '',
    offeringId = '',
    countLabel = I18N.countPrefix,
    listApiPath = '/api/admin/resources',
    uploadApiPath = '/api/admin/resources/upload',
}) {
    const [resources, setResources] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [searchName, setSearchName] = useState('');
    const [searchType, setSearchType] = useState('');
    const [detailVisible, setDetailVisible] = useState(false);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailData, setDetailData] = useState(null);
    const fileInputRef = useRef(null);

    const scopeQueryParams = useMemo(() => {
        const params = { teacher_username: username };
        if (courseId) params.course_id = courseId;
        if (offeringId) params.offering_id = offeringId;
        return params;
    }, [username, courseId, offeringId]);

    const scopeQueryString = useMemo(() => buildQueryString(scopeQueryParams), [scopeQueryParams]);

    const loadResources = useCallback(async ({ name = '', fileType = '' } = {}) => {
        if (!username) {
            setResources([]);
            setTotalCount(0);
            return;
        }

        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE_URL}${listApiPath}`, {
                params: {
                    ...scopeQueryParams,
                    name: name || undefined,
                    file_type: fileType || undefined,
                },
            });
            const payload = response.data || {};
            setResources(Array.isArray(payload.items) ? payload.items : []);
            setTotalCount(Number.isFinite(payload.total) ? payload.total : 0);
        } catch (error) {
            console.error('Failed to load resources:', error);
            alert(error.response?.data?.detail || I18N.loadFailed);
            setResources([]);
            setTotalCount(0);
        } finally {
            setLoading(false);
        }
    }, [listApiPath, scopeQueryParams, username]);

    useEffect(() => {
        loadResources({ name: '', fileType: '' });
    }, [loadResources]);

    const openUpload = () => {
        fileInputRef.current?.click();
    };

    const handleUploadChange = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        setUploading(true);
        try {
            await axios.post(`${API_BASE_URL}${uploadApiPath}`, formData, {
                params: scopeQueryParams,
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            await loadResources({ name: searchName, fileType: searchType });
            alert(I18N.uploadSuccess);
        } catch (error) {
            console.error('Failed to upload resource:', error);
            alert(error.response?.data?.detail || I18N.uploadFailed);
        } finally {
            setUploading(false);
        }
    };

    const handleSearch = () => {
        loadResources({ name: searchName, fileType: searchType });
    };

    const handleDelete = async (item) => {
        if (!window.confirm(`${I18N.deleteConfirmPrefix} "${item.filename}" ${I18N.deleteConfirmSuffix}`)) return;
        try {
            await axios.delete(`${API_BASE_URL}${listApiPath}/${item.id}`, {
                params: scopeQueryParams,
            });
            if (detailData?.id === item.id) {
                setDetailVisible(false);
                setDetailData(null);
            }
            await loadResources({ name: searchName, fileType: searchType });
            alert(I18N.deleted);
        } catch (error) {
            console.error('Failed to delete resource:', error);
            alert(error.response?.data?.detail || I18N.deleteFailed);
        }
    };

    const handleViewDetail = async (item) => {
        setDetailVisible(true);
        setDetailLoading(true);
        setDetailData(null);
        try {
            const response = await axios.get(`${API_BASE_URL}${listApiPath}/${item.id}`, {
                params: scopeQueryParams,
            });
            setDetailData(response.data || null);
        } catch (error) {
            console.error('Failed to load resource detail:', error);
            alert(error.response?.data?.detail || I18N.detailFailed);
            setDetailVisible(false);
        } finally {
            setDetailLoading(false);
        }
    };

    const closeDetail = () => {
        setDetailVisible(false);
        setDetailData(null);
    };

    const downloadHref = detailData?.download_url
        ? `${API_BASE_URL}${detailData.download_url}${scopeQueryString ? `?${scopeQueryString}` : ''}`
        : '';

    return (
        <div className="resource-file-management">
            <div className="resource-toolbar">
                <button className="resource-upload-btn" onClick={openUpload} disabled={uploading}>
                    {uploading ? I18N.uploading : I18N.upload}
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    className="resource-file-input"
                    accept=".pdf,.doc,.docx,.md,.markdown,.txt,.csv,.json,.ppt,.pptx,.xls,.xlsx"
                    onChange={handleUploadChange}
                />
                <div className="resource-search-group">
                    <input
                        type="text"
                        placeholder={I18N.searchPlaceholder}
                        value={searchName}
                        onChange={(event) => setSearchName(event.target.value)}
                    />
                    <select
                        value={searchType}
                        onChange={(event) => setSearchType(event.target.value)}
                    >
                        {FILE_TYPE_OPTIONS.map((option) => (
                            <option key={option.value || 'all'} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                    <button className="resource-search-btn" onClick={handleSearch}>
                        {I18N.search}
                    </button>
                    <span className="resource-count">{`${countLabel} ${totalCount}`}</span>
                </div>
            </div>

            <div className="resource-table-wrap">
                <table className="resource-table">
                    <thead>
                        <tr>
                            <th>{I18N.tableFilename}</th>
                            <th>{I18N.tableType}</th>
                            <th>{I18N.tableCreatedAt}</th>
                            <th>{I18N.tableAction}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan="4" className="resource-empty-row">{I18N.loading}</td>
                            </tr>
                        ) : resources.length === 0 ? (
                            <tr>
                                <td colSpan="4" className="resource-empty-row">{I18N.empty}</td>
                            </tr>
                        ) : (
                            resources.map((item) => (
                                <tr key={item.id}>
                                    <td>{item.filename}</td>
                                    <td>{item.file_type || '-'}</td>
                                    <td>{formatDate(item.created_at)}</td>
                                    <td>
                                        <button className="resource-link-btn detail" onClick={() => handleViewDetail(item)}>
                                            {I18N.detail}
                                        </button>
                                        <button className="resource-link-btn delete" onClick={() => handleDelete(item)}>
                                            {I18N.del}
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {detailVisible && (
                <div className="resource-modal-mask" onClick={closeDetail}>
                    <div className="resource-modal" onClick={(event) => event.stopPropagation()}>
                        <div className="resource-modal-header">
                            <h3>{detailData?.filename || I18N.detailTitle}</h3>
                            <button onClick={closeDetail}>{I18N.close}</button>
                        </div>
                        <div className="resource-modal-body">
                            {detailLoading ? (
                                <div className="resource-preview-empty">{I18N.detailLoading}</div>
                            ) : (
                                <ResourcePreviewContent
                                    detailData={detailData}
                                    accessQueryKey="teacher_username"
                                    accessQueryValue={username}
                                    accessQueryParams={scopeQueryParams}
                                    loadingText={I18N.previewLoading}
                                    emptyText={I18N.previewEmpty}
                                    unsupportedText={I18N.previewUnsupported}
                                />
                            )}
                        </div>
                        {!detailLoading && detailData && downloadHref ? (
                            <div className="resource-modal-footer">
                                <a
                                    href={downloadHref}
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    {I18N.download}
                                </a>
                            </div>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
}

export default ResourceFileManagement;
