import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import ResourcePreviewContent from '../../../shared/resource-preview/ResourcePreviewContent';

function StudentResourcePanel({
    username,
    courseId = '',
    offeringId = '',
    countPrefix,
    countSuffix,
    emptyText,
    searchPlaceholder,
    apiBaseUrl,
    text,
    resourceTypeOptions,
    buildQueryString,
    formatDateTime,
}) {
    const [resources, setResources] = useState([]);
    const [resourceLoading, setResourceLoading] = useState(false);
    const [searchName, setSearchName] = useState('');
    const [searchType, setSearchType] = useState('');
    const [totalCount, setTotalCount] = useState(0);
    const [detailVisible, setDetailVisible] = useState(false);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailData, setDetailData] = useState(null);

    const scopeParams = useMemo(() => {
        const params = {
            student_id: username,
        };
        if (courseId) params.course_id = courseId;
        if (offeringId) params.offering_id = offeringId;
        return params;
    }, [courseId, offeringId, username]);

    const scopeQueryString = useMemo(() => buildQueryString(scopeParams), [buildQueryString, scopeParams]);

    const loadResources = async ({ name = searchName, fileType = searchType } = {}) => {
        if (!username || (!courseId && !offeringId)) {
            setResources([]);
            setTotalCount(0);
            return;
        }

        setResourceLoading(true);
        try {
            const response = await axios.get(`${apiBaseUrl}/api/student/resources`, {
                params: {
                    ...scopeParams,
                    name: name || undefined,
                    file_type: fileType || undefined
                }
            });
            const payload = response.data || {};
            setResources(Array.isArray(payload.items) ? payload.items : []);
            setTotalCount(Number.isFinite(payload.total) ? payload.total : 0);
        } catch (error) {
            console.error('Failed to load student resources:', error);
            alert(text.resourceLoadError);
        } finally {
            setResourceLoading(false);
        }
    };

    useEffect(() => {
        loadResources({ name: '', fileType: '' });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [courseId, offeringId, username]);

    const openResourceDetail = async (resourceId) => {
        setDetailVisible(true);
        setDetailLoading(true);
        setDetailData(null);
        try {
            const response = await axios.get(`${apiBaseUrl}/api/student/resources/${resourceId}`, {
                params: scopeParams
            });
            setDetailData(response.data || null);
        } catch (error) {
            console.error('Failed to load resource detail:', error);
            alert(error.response?.data?.detail || text.resourceDetailError);
            setDetailVisible(false);
        } finally {
            setDetailLoading(false);
        }
    };

    return (
        <div className="lab-resource-panel">
            <div className="lab-resource-toolbar">
                <div className="lab-resource-search">
                    <input
                        type="text"
                        placeholder={searchPlaceholder}
                        value={searchName}
                        onChange={(event) => setSearchName(event.target.value)}
                    />
                    <select value={searchType} onChange={(event) => setSearchType(event.target.value)}>
                        {resourceTypeOptions.map((item) => (
                            <option key={item.value || 'all'} value={item.value}>
                                {item.label}
                            </option>
                        ))}
                    </select>
                    <button type="button" onClick={() => loadResources()}>
                        {text.resourceSearch}
                    </button>
                </div>
                <span className="lab-resource-total">{`${countPrefix}${totalCount}${countSuffix}`}</span>
            </div>

            <div className="lab-resource-table-wrap">
                <table className="lab-resource-table">
                    <thead>
                        <tr>
                            <th>{text.resourceFileName}</th>
                            <th>{text.resourceFileType}</th>
                            <th>{text.resourceCreatedAt}</th>
                            <th>{text.operation}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {resourceLoading ? (
                            <tr>
                                <td colSpan="4" className="lab-resource-empty-row">{text.resourceLoading}</td>
                            </tr>
                        ) : resources.length === 0 ? (
                            <tr>
                                <td colSpan="4" className="lab-resource-empty-row">{emptyText}</td>
                            </tr>
                        ) : (
                            resources.map((resource) => (
                                <tr key={resource.id}>
                                    <td>{resource.filename}</td>
                                    <td>{resource.file_type || '-'}</td>
                                    <td>{formatDateTime(resource.created_at)}</td>
                                    <td>
                                        <button
                                            type="button"
                                            className="lab-resource-link detail"
                                            onClick={() => openResourceDetail(resource.id)}
                                        >
                                            {text.detail}
                                        </button>
                                        <button
                                            type="button"
                                            className="lab-resource-link download"
                                            onClick={() => window.open(`${apiBaseUrl}/api/student/resources/${resource.id}/download?${scopeQueryString}`, '_blank')}
                                        >
                                            {text.download}
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {detailVisible ? (
                <div className="lab-resource-modal-mask" onClick={() => setDetailVisible(false)}>
                    <div className="lab-resource-modal" onClick={(event) => event.stopPropagation()}>
                        <div className="lab-resource-modal-header">
                            <h3>{detailData?.filename || text.detail}</h3>
                            <button type="button" onClick={() => setDetailVisible(false)}>{text.close}</button>
                        </div>
                        <div className="lab-resource-modal-body">
                            {detailLoading ? (
                                <div className="lab-resource-preview-empty">{text.resourceLoading}</div>
                            ) : (
                                <ResourcePreviewContent
                                    detailData={detailData}
                                    accessQueryKey="student_id"
                                    accessQueryValue={username}
                                    accessQueryParams={scopeParams}
                                    loadingText={text.resourceLoading}
                                    emptyText={text.noPreviewContent}
                                    unsupportedText={text.unsupportedPreview}
                                />
                            )}
                        </div>
                        {detailData ? (
                            <div className="lab-resource-modal-footer">
                                <button
                                    type="button"
                                    className="lab-resource-download-btn"
                                    onClick={() => window.open(`${apiBaseUrl}/api/student/resources/${detailData.id}/download?${scopeQueryString}`, '_blank')}
                                >
                                    {text.download}
                                </button>
                            </div>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </div>
    );
}

export default StudentResourcePanel;
