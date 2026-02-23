import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { QRCodeCanvas } from 'qrcode.react';
import './TeacherUserManagement.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

function normalizeOptions(items) {
    if (!Array.isArray(items)) return [];
    return items
        .map((item) => {
            const id = String(item?.id ?? '').trim();
            const value = String(item?.value ?? item?.name ?? '').trim();
            const label = String(item?.label ?? value).trim();
            if (!value) return null;
            return { id, value, label: label || value };
        })
        .filter(Boolean);
}

function normalizeOfferings(items, courseId) {
    if (!Array.isArray(items)) return [];
    const normalizedCourseId = String(courseId || '').trim();
    return items
        .filter((item) => {
            const offeringCourseId = String(item?.template_course_id || item?.course_id || '').trim();
            if (offeringCourseId !== normalizedCourseId) return false;
            const status = String(item?.status || '').trim().toLowerCase();
            // Hide archived offerings in class management panel to support "remove" UX on older backends.
            return status !== 'archived';
        })
        .map((item) => {
            const className = String(item?.class_name || '').trim();
            if (!className) return null;
            return {
                offeringId: String(item?.offering_id ?? item?.id ?? '').trim(),
                className,
                offeringCode: String(item?.offering_code || '').trim() || '-',
                joinCode: String(item?.join_code || '').trim() || '-',
                term: String(item?.term || '').trim() || '-',
                status: String(item?.status || '').trim() || '-',
                updatedAt: item?.updated_at || item?.created_at || null,
            };
        })
        .filter(Boolean)
        .sort((a, b) => new Date(b.updatedAt || 0).getTime() - new Date(a.updatedAt || 0).getTime());
}

function TeacherUserManagement({ username, courseId = '', onRosterChanged }) {
    const normalizedCourseId = String(courseId || '').trim();
    const studentApiBase = useMemo(
        () => `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(normalizedCourseId)}/students`,
        [normalizedCourseId]
    );
    const notifyRosterChanged = useCallback(() => {
        if (typeof onRosterChanged === 'function') onRosterChanged();
    }, [onRosterChanged]);

    const [students, setStudents] = useState([]);
    const [classes, setClasses] = useState([]);
    const [admissionYears, setAdmissionYears] = useState([]);
    const [keyword, setKeyword] = useState('');
    const [classFilter, setClassFilter] = useState('');
    const [admissionYearFilter, setAdmissionYearFilter] = useState('');
    const [page, setPage] = useState(1);
    const [pageSize] = useState(20);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const [importResult, setImportResult] = useState(null);

    const [showAddClassModeModal, setShowAddClassModeModal] = useState(false);
    const [showClassImportModal, setShowClassImportModal] = useState(false);
    const [classImportFile, setClassImportFile] = useState(null);
    const [classImportResult, setClassImportResult] = useState(null);
    const [importingClasses, setImportingClasses] = useState(false);

    const [offerings, setOfferings] = useState([]);
    const [loadingOfferings, setLoadingOfferings] = useState(false);
    const [generatingClassName, setGeneratingClassName] = useState('');
    const [removingClassKey, setRemovingClassKey] = useState('');
    const [showCreateClassModal, setShowCreateClassModal] = useState(false);
    const [creatingClass, setCreatingClass] = useState(false);
    const [qrModal, setQrModal] = useState({ open: false, item: null });
    const addClassMenuRef = useRef(null);
    const [classForm, setClassForm] = useState({
        class_name: '',
        term: '',
        major: '',
        offering_code: '',
    });

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [pageSize, total]);

    const loadStudents = useCallback(async ({ targetPage = 1, targetKeyword = '', targetClass = '', targetAdmissionYear = '' } = {}) => {
        if (!normalizedCourseId) return;
        setLoading(true);
        try {
            const res = await axios.get(studentApiBase, {
                params: {
                    teacher_username: username,
                    keyword: targetKeyword,
                    class_name: targetClass,
                    admission_year: targetAdmissionYear,
                    page: targetPage,
                    page_size: pageSize,
                }
            });
            const payload = res.data || {};
            setStudents(Array.isArray(payload.items) ? payload.items : []);
            setTotal(Number(payload.total || 0));
            setPage(Number(payload.page || targetPage));
        } catch (error) {
            alert(error.response?.data?.detail || '加载课程学生失败');
        } finally {
            setLoading(false);
        }
    }, [normalizedCourseId, pageSize, studentApiBase, username]);

    const loadClassAndYearOptions = useCallback(async () => {
        if (!normalizedCourseId) return;
        try {
            const [classRes, yearRes] = await Promise.all([
                axios.get(`${studentApiBase}/classes`, { params: { teacher_username: username } }),
                axios.get(`${studentApiBase}/admission-years`, { params: { teacher_username: username } }),
            ]);
            setClasses(normalizeOptions(classRes.data));
            setAdmissionYears(normalizeOptions(yearRes.data));
        } catch (error) {
            setClasses([]);
            setAdmissionYears([]);
        }
    }, [normalizedCourseId, studentApiBase, username]);

    const loadOfferings = useCallback(async () => {
        if (!normalizedCourseId) return;
        setLoadingOfferings(true);
        try {
            const res = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
                params: { teacher_username: username }
            });
            setOfferings(normalizeOfferings(res.data, normalizedCourseId));
        } catch (error) {
            setOfferings([]);
            alert(error.response?.data?.detail || '加载班级列表失败');
        } finally {
            setLoadingOfferings(false);
        }
    }, [normalizedCourseId, username]);

    const refreshClassPanel = useCallback(async () => {
        await loadOfferings();
    }, [loadOfferings]);

    // Merge class master data with offering records so classes without join codes still appear in the table.
    const classCodeRows = useMemo(() => {
        const byClassName = new Map();
        offerings.forEach((item) => {
            const className = String(item.className || '').trim();
            if (!className || className === '-' || byClassName.has(className)) return;
            byClassName.set(className, item);
        });

        const names = new Set([
            ...classes.map((item) => String(item.value || '').trim()).filter(Boolean),
            ...Array.from(byClassName.keys()),
        ]);

        return Array.from(names)
            .sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
            .map((name) => {
                const existing = byClassName.get(name);
                if (existing) return { ...existing, classId: '', isPlaceholder: false };
                return {
                    offeringId: '',
                    classId: '',
                    className: name,
                    offeringCode: '-',
                    joinCode: '-',
                    term: '-',
                    status: '暂无课程码',
                    isPlaceholder: true,
                };
            });
    }, [classes, offerings]);

    // Close the add-class menu on outside click or Escape for predictable popover behavior.
    useEffect(() => {
        loadStudents();
        loadClassAndYearOptions();
        refreshClassPanel();
    }, [loadStudents, loadClassAndYearOptions, refreshClassPanel]);

    useEffect(() => {
        if (!showAddClassModeModal) return undefined;

        const handleDocumentMouseDown = (event) => {
            if (addClassMenuRef.current && !addClassMenuRef.current.contains(event.target)) {
                setShowAddClassModeModal(false);
            }
        };
        const handleDocumentKeyDown = (event) => {
            if (event.key === 'Escape') setShowAddClassModeModal(false);
        };

        document.addEventListener('mousedown', handleDocumentMouseDown);
        document.addEventListener('keydown', handleDocumentKeyDown);
        return () => {
            document.removeEventListener('mousedown', handleDocumentMouseDown);
            document.removeEventListener('keydown', handleDocumentKeyDown);
        };
    }, [showAddClassModeModal]);

    const handleSearch = () => loadStudents({
        targetPage: 1,
        targetKeyword: keyword,
        targetClass: classFilter,
        targetAdmissionYear: admissionYearFilter,
    });

    const handleResetSearch = () => {
        setKeyword('');
        setClassFilter('');
        setAdmissionYearFilter('');
        loadStudents();
    };

    const handleDownloadTemplate = async (format) => {
        try {
            const res = await axios.get(`${studentApiBase}/template`, {
                params: { teacher_username: username, format },
                responseType: 'blob'
            });
            const blob = new Blob([res.data]);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `student_import_template.${format}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.response?.data?.detail || '下载模板失败');
        }
    };

    const autoCreateOfferingsForClasses = useCallback(async (classNames) => {
        let names = Array.from(
            new Set(
                (Array.isArray(classNames) ? classNames : [])
                    .map((item) => String(item || '').trim())
                    .filter(Boolean)
            )
        );
        if (!normalizedCourseId) {
            return { createdCount: 0, failed: [] };
        }
        // Fallback for older backend responses that don't return imported class names.
        if (names.length === 0) {
            try {
                const classRes = await axios.get(`${studentApiBase}/classes`, {
                    params: { teacher_username: username },
                });
                names = normalizeOptions(classRes.data)
                    .map((item) => String(item?.value || '').trim())
                    .filter(Boolean);
            } catch (error) {
                names = [];
            }
        }
        if (names.length === 0) return { createdCount: 0, failed: [] };

        const existingRes = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
            params: { teacher_username: username },
        });
        const existingClassNames = new Set(
            normalizeOfferings(existingRes.data, normalizedCourseId)
                .map((item) => String(item.className || '').trim())
                .filter(Boolean)
        );

        let createdCount = 0;
        const failed = [];
        for (const className of names) {
            if (existingClassNames.has(className)) continue;
            try {
                await axios.post(`${API_BASE_URL}/api/teacher/offerings`, {
                    teacher_username: username,
                    template_course_id: normalizedCourseId,
                    class_name: className,
                });
                createdCount += 1;
                existingClassNames.add(className);
            } catch (error) {
                const status = Number(error?.response?.status || 0);
                if (status === 409) {
                    existingClassNames.add(className);
                    continue;
                }
                failed.push({
                    className,
                    reason: error?.response?.data?.detail || '生成课程码失败',
                });
            }
        }

        if (createdCount > 0) {
            await refreshClassPanel();
            notifyRosterChanged();
        }
        return { createdCount, failed };
    }, [normalizedCourseId, notifyRosterChanged, refreshClassPanel, studentApiBase, username]);

    const handleImportStudents = async () => {
        if (!selectedFile) {
            alert('请先选择文件');
            return;
        }
        const formData = new FormData();
        formData.append('file', selectedFile);
        try {
            const res = await axios.post(`${studentApiBase}/import`, formData, {
                params: { teacher_username: username },
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const payload = res.data || null;
            setImportResult(payload);
            const autoCreateResult = await autoCreateOfferingsForClasses(payload?.imported_class_names);
            if (autoCreateResult.failed.length > 0) {
                const firstFailed = autoCreateResult.failed[0];
                alert(`部分班级课程码自动生成失败：${firstFailed.className}（${firstFailed.reason}）`);
            }
            await loadStudents({
                targetPage: 1,
                targetKeyword: keyword,
                targetClass: classFilter,
                targetAdmissionYear: admissionYearFilter,
            });
            await loadClassAndYearOptions();
            await refreshClassPanel();
            notifyRosterChanged();
        } catch (error) {
            alert(error.response?.data?.detail || '导入失败');
        }
    };

    const handleChooseCreateClassMode = (mode) => {
        setShowAddClassModeModal(false);
        if (mode === 'manual') {
            setShowCreateClassModal(true);
            return;
        }
        setClassImportFile(null);
        setClassImportResult(null);
        setShowClassImportModal(true);
    };
    const handleDownloadClassTemplate = async (format) => {
        try {
            const res = await axios.get(`${API_BASE_URL}/api/admin/classes/template`, {
                params: { teacher_username: username, format },
                responseType: 'blob'
            });
            const blob = new Blob([res.data]);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `class_import_template.${format}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.response?.data?.detail || '下载模板失败');
        }
    };

    const handleImportClasses = async () => {
        if (!classImportFile) {
            alert('请先选择文件');
            return;
        }
        const formData = new FormData();
        formData.append('file', classImportFile);
        setImportingClasses(true);
        try {
            const res = await axios.post(`${API_BASE_URL}/api/admin/classes/import`, formData, {
                params: { teacher_username: username },
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const payload = res.data || null;
            setClassImportResult(payload);
            const autoCreateResult = await autoCreateOfferingsForClasses(payload?.created_class_names);
            if (autoCreateResult.failed.length > 0) {
                const firstFailed = autoCreateResult.failed[0];
                alert(`部分班级课程码自动生成失败：${firstFailed.className}（${firstFailed.reason}）`);
            }
            setClassImportFile(null);
            await refreshClassPanel();
            await loadClassAndYearOptions();
            await loadStudents({
                targetPage: 1,
                targetKeyword: keyword,
                targetClass: classFilter,
                targetAdmissionYear: admissionYearFilter
            });
            notifyRosterChanged();
        } catch (error) {
            alert(error.response?.data?.detail || '导入失败');
        } finally {
            setImportingClasses(false);
        }
    };

    const handleCreateClass = async () => {
        const className = String(classForm.class_name || '').trim();
        if (!className) {
            alert('请输入班级名称');
            return;
        }
        setCreatingClass(true);
        try {
            await axios.post(`${API_BASE_URL}/api/teacher/offerings`, {
                teacher_username: username,
                template_course_id: normalizedCourseId,
                class_name: className,
                term: String(classForm.term || '').trim() || null,
                major: String(classForm.major || '').trim() || null,
                offering_code: String(classForm.offering_code || '').trim() || null,
            });
            setClassForm({ class_name: '', term: '', major: '', offering_code: '' });
            setShowCreateClassModal(false);
            await refreshClassPanel();
            notifyRosterChanged();
            alert('班级创建成功');
        } catch (error) {
            alert(error.response?.data?.detail || '创建班级失败');
        } finally {
            setCreatingClass(false);
        }
    };

    const handleGenerateCodeForClass = async (className) => {
        const targetClassName = String(className || '').trim();
        if (!targetClassName) return;
        if (offerings.some((item) => String(item.className || '').trim() === targetClassName)) {
            alert('该班级已存在课程码');
            return;
        }
        setGeneratingClassName(targetClassName);
        try {
            await axios.post(`${API_BASE_URL}/api/teacher/offerings`, {
                teacher_username: username,
                template_course_id: normalizedCourseId,
                class_name: targetClassName,
            });
            await refreshClassPanel();
            notifyRosterChanged();
            alert('课程码已生成');
        } catch (error) {
            alert(error.response?.data?.detail || '生成课程码失败');
        } finally {
            setGeneratingClassName('');
        }
    };

    const handleCopyJoinCode = async (joinCode) => {
        const code = String(joinCode || '').trim();
        if (!code || code === '-') return;
        try {
            await navigator.clipboard.writeText(code);
            alert('课程码已复制');
        } catch (error) {
            alert('复制失败，请手动复制');
        }
    };

    const classRowActionKey = (item) => String(item?.offeringId || item?.classId || `class-${item?.className || ''}`);
    // Backend compatibility: try DELETE first, then PATCH with different payload styles on older deployments.
    const removeOfferingWithFallback = useCallback(async (offeringId) => {
        const normalizedOfferingId = String(offeringId || '').trim();
        if (!normalizedOfferingId) return false;
        const url = `${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(normalizedOfferingId)}`;
        try {
            await axios.delete(url, {
                params: { teacher_username: username }
            });
            return true;
        } catch (error) {
            const status = Number(error?.response?.status || 0);
            if (status === 404) return true;
            if (status !== 405) throw error;
        }
        try {
            await axios.patch(url, {
                teacher_username: username,
                status: 'archived',
            });
            return true;
        } catch (patchError) {
            const patchStatus = Number(patchError?.response?.status || 0);
            if (patchStatus === 404) return true;
            if (patchStatus !== 400 && patchStatus !== 422) throw patchError;
        }
        await axios.patch(url, null, {
            params: {
                teacher_username: username,
                status: 'archived',
            },
        });
        return true;
    }, [username]);

    const findClassOfferings = useCallback(async (className) => {
        const normalizedClassName = String(className || '').trim();
        if (!normalizedClassName) return [];
        const fromState = offerings.filter((item) => String(item?.className || '').trim() === normalizedClassName);
        if (fromState.length > 0) return fromState;
        const res = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
            params: { teacher_username: username },
        });
        return normalizeOfferings(res.data, normalizedCourseId)
            .filter((item) => String(item?.className || '').trim() === normalizedClassName);
    }, [normalizedCourseId, offerings, username]);

    const handleRemoveClass = async (item) => {
        const offeringId = String(item?.offeringId || '').trim();
        const classId = String(item?.classId || '').trim();
        const className = String(item?.className || '').trim();
        if (!className) return;

        const confirmText = offeringId
            ? `确认将班级“${className}”从当前课程移除吗？移除后课程码将失效。`
            : `确认删除班级“${className}”吗？`;
        if (!window.confirm(confirmText)) return;

        const actionKey = classRowActionKey(item);
        setRemovingClassKey(actionKey);
        try {
            if (offeringId) {
                await removeOfferingWithFallback(offeringId);
            } else if (classId) {
                await axios.delete(`${API_BASE_URL}/api/admin/classes/${encodeURIComponent(classId)}`, {
                    params: { teacher_username: username }
                });
            } else {
                alert('缺少班级标识，请刷新后重试');
                return;
            }

            await refreshClassPanel();
            await loadClassAndYearOptions();
            await loadStudents({
                targetPage: 1,
                targetKeyword: keyword,
                targetClass: classFilter,
                targetAdmissionYear: admissionYearFilter,
            });
            notifyRosterChanged();
            alert(offeringId ? '已从当前课程移除班级' : '班级已删除');
        } catch (error) {
            alert(error.response?.data?.detail || (offeringId ? '移除班级失败' : '删除班级失败'));
        } finally {
            setRemovingClassKey('');
        }
    };

    const getJoinUrl = (joinCode) => {
        const code = String(joinCode || '').trim();
        if (!code || code === '-') return '';
        return `${window.location.origin}/student/join?code=${encodeURIComponent(code)}`;
    };

    const handleResetPassword = async (studentId) => {
        if (!window.confirm(`确认将 ${studentId} 的密码重置为 123456 吗？`)) return;
        try {
            await axios.post(`${studentApiBase}/${encodeURIComponent(studentId)}/reset-password`, null, {
                params: { teacher_username: username }
            });
            alert('密码重置成功');
        } catch (error) {
            alert(error.response?.data?.detail || '密码重置失败');
        }
    };

    const handleRemoveStudent = async (studentId) => {
        if (!window.confirm(`确认将 ${studentId} 移出该课程吗？`)) return;
        try {
            await axios.delete(`${studentApiBase}/${encodeURIComponent(studentId)}`, {
                params: { teacher_username: username }
            });
            await loadStudents({ targetPage: 1, targetKeyword: keyword, targetClass: classFilter, targetAdmissionYear: admissionYearFilter });
            notifyRosterChanged();
            alert('学生已移出课程');
        } catch (error) {
            alert(error.response?.data?.detail || '移出学生失败');
        }
    };

    const handleBatchRemoveByClass = async () => {
        if (!classFilter) {
            alert('请先选择班级');
            return;
        }
        if (!window.confirm(`确认移出班级“${classFilter}”的全部学生吗？`)) return;
        try {
            const targetClassName = String(classFilter || '').trim();
            await axios.delete(studentApiBase, {
                params: { teacher_username: username, class_name: targetClassName }
            });
            // Keep class join-code state aligned after class-level student removal.
            const matchedOfferings = await findClassOfferings(targetClassName);
            for (const item of matchedOfferings) {
                await removeOfferingWithFallback(item.offeringId);
            }
            await loadStudents({ targetPage: 1, targetKeyword: keyword, targetClass: classFilter, targetAdmissionYear: admissionYearFilter });
            await loadClassAndYearOptions();
            notifyRosterChanged();
            await refreshClassPanel();
            alert('批量移出完成');
        } catch (error) {
            alert(error.response?.data?.detail || '批量移出失败');
        }
    };
    const handleRefreshClassPanel = useCallback(async () => {
        const autoCreateResult = await autoCreateOfferingsForClasses();
        if (autoCreateResult.failed.length > 0) {
            const firstFailed = autoCreateResult.failed[0];
            alert(`部分班级课程码自动生成失败：${firstFailed.className}（${firstFailed.reason}）`);
        }
        await refreshClassPanel();
        notifyRosterChanged();
    }, [autoCreateOfferingsForClasses, notifyRosterChanged, refreshClassPanel]);

    if (!normalizedCourseId) {
    return <div className="user-placeholder">请先选择课程。</div>;
}

return (
    <div className="user-management">
        <div className="user-management-toolbar">
            <h2>课程学生管理</h2>
            <div className="user-management-actions">
                <div className="add-class-trigger" ref={addClassMenuRef}>
                    <button onClick={() => setShowAddClassModeModal((prev) => !prev)}>添加班级</button>
                    {showAddClassModeModal ? (
                        <div className="add-class-dropdown">
                            <button onClick={() => handleChooseCreateClassMode('manual')}>手动添加</button>
                            <button onClick={() => handleChooseCreateClassMode('batch')}>批量导入</button>
                        </div>
                    ) : null}
                </div>
                <button onClick={handleRefreshClassPanel}>刷新班级</button>
                <button onClick={() => { setShowImportModal(true); setSelectedFile(null); setImportResult(null); }}>导入学生</button>
            </div>
        </div>

        <div className="course-offering-panel">
            <div className="course-offering-head">
                <strong>班级与课程码</strong>
                <span>可为已导入的班级生成课程码，并在需要时移除班级。</span>
            </div>
            {loadingOfferings ? (
                <div className="user-placeholder">正在加载班级...</div>
            ) : classCodeRows.length === 0 ? (
                <div className="user-placeholder">暂无班级。</div>
            ) : (
                <div className="user-table-wrap">
                    <table className="user-table">
                        <thead>
                            <tr>
                                <th>班级名称</th>
                                <th>开课代码</th>
                                <th>课程码</th>
                                <th>学期</th>
                                <th>状态</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {classCodeRows.map((item) => (
                                <tr key={classRowActionKey(item)}>
                                    <td>{item.className}</td>
                                    <td>{item.offeringCode}</td>
                                    <td>{item.joinCode}</td>
                                    <td>{item.term}</td>
                                    <td>{item.status}</td>
                                    <td>
                                        {item.isPlaceholder ? (
                                            <>
                                                <button
                                                    onClick={() => handleGenerateCodeForClass(item.className)}
                                                    disabled={generatingClassName === item.className}
                                                >
                                                    {generatingClassName === item.className ? '生成中...' : '生成课程码'}
                                                </button>
                                                {item.classId ? (
                                                    <button
                                                        className="danger-btn"
                                                        onClick={() => handleRemoveClass(item)}
                                                        disabled={removingClassKey === classRowActionKey(item)}
                                                    >
                                                        {removingClassKey === classRowActionKey(item) ? '移除中...' : '移除班级'}
                                                    </button>
                                                ) : null}
                                            </>
                                        ) : (
                                            <>
                                                <button onClick={() => handleCopyJoinCode(item.joinCode)}>复制码</button>
                                                <button onClick={() => setQrModal({ open: true, item })}>显示二维码</button>
                                                <button
                                                    className="danger-btn"
                                                    onClick={() => handleRemoveClass(item)}
                                                    disabled={removingClassKey === classRowActionKey(item)}
                                                >
                                                    {removingClassKey === classRowActionKey(item) ? '移除中...' : '移除班级'}
                                                </button>
                                            </>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>

        <div className="user-filters">
            <input type="text" placeholder="按学号或姓名搜索" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            <select value={classFilter} onChange={(e) => setClassFilter(e.target.value)}>
                <option value="">全部班级</option>
                {classes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <select value={admissionYearFilter} onChange={(e) => setAdmissionYearFilter(e.target.value)}>
                <option value="">全部入学年份</option>
                {admissionYears.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <button onClick={handleSearch}>搜索</button>
            <button onClick={handleResetSearch}>重置</button>
            <button className="danger-btn" disabled={!classFilter || loading} onClick={handleBatchRemoveByClass}>移出当前班级学生</button>
        </div>

        <div className="user-table-wrap">
            {loading ? (
                <div className="user-placeholder">正在加载学生...</div>
            ) : students.length === 0 ? (
                <div className="user-placeholder">未找到学生。</div>
            ) : (
                <table className="user-table">
                    <thead>
                        <tr>
                            <th>用户名</th>
                            <th>学号</th>
                            <th>组织</th>
                            <th>姓名</th>
                            <th>入学年份</th>
                            <th>班级</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {students.map((item) => (
                            <tr key={item.student_id || item.username}>
                                <td>{item.username || '-'}</td>
                                <td>{item.student_id || '-'}</td>
                                <td>{item.organization || '-'}</td>
                                <td>{item.real_name || '-'}</td>
                                <td>{item.admission_year_label || (item.admission_year ? (String(item.admission_year) + '级') : '-')}</td>
                                <td>{item.class_name || '-'}</td>
                                <td>
                                    <button onClick={() => handleResetPassword(item.student_id)}>重置密码</button>
                                    <button className="danger-btn" onClick={() => handleRemoveStudent(item.student_id)}>移出课程</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>

        <div className="user-pagination">
            <span>共 {total} 条</span>
            <button disabled={page <= 1} onClick={() => loadStudents({ targetPage: page - 1, targetKeyword: keyword, targetClass: classFilter, targetAdmissionYear: admissionYearFilter })}>上一页</button>
            <span>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => loadStudents({ targetPage: page + 1, targetKeyword: keyword, targetClass: classFilter, targetAdmissionYear: admissionYearFilter })}>下一页</button>
        </div>

        {showImportModal ? (
            <div className="user-modal-overlay" onClick={() => setShowImportModal(false)}>
                <div className="user-modal class-import-modal student-import-modal" onClick={(e) => e.stopPropagation()}>
                    <div className="class-import-title-row">
                        <h3>导入学生</h3>
                        <button
                            type="button"
                            className="class-import-close-btn"
                            onClick={() => setShowImportModal(false)}
                        >
                            关闭
                        </button>
                    </div>
                    <div className="class-import-panel">
                        <div className="class-import-header">
                            <span>批量导入格式：学号 / 姓名 / 入学年份 / 班级</span>
                            <div className="class-import-template-actions">
                                <button onClick={() => handleDownloadTemplate('xlsx')}>下载模板（xlsx）</button>
                                <button onClick={() => handleDownloadTemplate('csv')}>下载模板（csv）</button>
                            </div>
                        </div>
                        <div className="class-import-input-row">
                            <input type="file" accept=".xlsx,.csv" onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} />
                            <button onClick={handleImportStudents}>开始导入</button>
                        </div>
                        <div className="import-file-name">{selectedFile ? ('已选择：' + selectedFile.name) : '未选择文件'}</div>
                    </div>
                    {importResult ? (
                        <div className="import-result">
                            <p>总行数：{importResult.total_rows}</p>
                            <p>成功：{importResult.success_count}</p>
                            <p>跳过：{importResult.skipped_count}</p>
                            <p>新增：{importResult.created_count ?? 0}</p>
                            <p>失败：{importResult.failed_count}</p>
                            {Array.isArray(importResult.errors) && importResult.errors.length > 0 ? (
                                <div className="import-errors">
                                    <h4>导入错误</h4>
                                    <ul>
                                        {importResult.errors.slice(0, 20).map((item, index) => (
                                            <li key={(item.row || index) + '-' + (item.reason || '')}>
                                                {'第 ' + (item.row || '-') + ' 行：' + (item.reason || '导入失败')}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ) : null}
                        </div>
                    ) : null}
                </div>
            </div>
        ) : null}

        {showClassImportModal ? (
            <div className="user-modal-overlay" onClick={() => setShowClassImportModal(false)}>
                <div className="user-modal class-import-modal" onClick={(e) => e.stopPropagation()}>
                    <div className="class-import-title-row">
                        <h3>班级管理</h3>
                        <button
                            type="button"
                            className="class-import-close-btn"
                            onClick={() => setShowClassImportModal(false)}
                            disabled={importingClasses}
                        >
                            关闭
                        </button>
                    </div>
                    <div className="class-import-panel">
                        <div className="class-import-header">
                            <span>批量导入格式：入学年级 / 专业 / 班级</span>
                            <div className="class-import-template-actions">
                            <button onClick={() => handleDownloadClassTemplate('xlsx')}>下载班级模板（xlsx）</button>
                            <button onClick={() => handleDownloadClassTemplate('csv')}>下载班级模板（csv）</button>
                            </div>
                        </div>
                        <div className="class-import-input-row">
                            <input
                                type="file"
                                accept=".xlsx,.csv"
                                onChange={(e) => setClassImportFile(e.target.files?.[0] || null)}
                                disabled={importingClasses}
                            />
                            <button onClick={handleImportClasses} disabled={importingClasses}>
                                {importingClasses ? '导入中...' : '上传并导入班级'}
                            </button>
                        </div>
                        <div className="import-file-name">{classImportFile ? ('已选择：' + classImportFile.name) : '未选择班级导入文件'}</div>
                    </div>
                    {classImportResult ? (
                        <div className="import-result">
                            <p>总行数：{classImportResult.total_rows}</p>
                            <p>成功：{classImportResult.success_count}</p>
                            <p>跳过：{classImportResult.skipped_count}</p>
                            <p>失败：{classImportResult.failed_count}</p>
                            {Array.isArray(classImportResult.errors) && classImportResult.errors.length > 0 ? (
                                <div className="import-errors">
                                    <h4>导入错误</h4>
                                    <ul>
                                        {classImportResult.errors.slice(0, 20).map((item, index) => (
                                            <li key={(item.row || index) + '-' + (item.reason || '')}>
                                                {'第 ' + (item.row || '-') + ' 行：' + (item.reason || '导入失败')}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ) : null}
                        </div>
                    ) : null}
                </div>
            </div>
        ) : null}

        {showCreateClassModal ? (
            <div className="user-modal-overlay" onClick={() => setShowCreateClassModal(false)}>
                <div className="user-modal" onClick={(e) => e.stopPropagation()}>
                    <h3>创建班级</h3>
                    <div className="class-create-row">
                        <input
                            type="text"
                            placeholder="班级名称（必填）"
                            value={classForm.class_name}
                            onChange={(e) => setClassForm((prev) => ({ ...prev, class_name: e.target.value }))}
                        />
                    </div>
                    <div className="class-create-row">
                        <input
                            type="text"
                            placeholder="学期（可选）"
                            value={classForm.term}
                            onChange={(e) => setClassForm((prev) => ({ ...prev, term: e.target.value }))}
                        />
                        <input
                            type="text"
                            placeholder="专业（可选）"
                            value={classForm.major}
                            onChange={(e) => setClassForm((prev) => ({ ...prev, major: e.target.value }))}
                        />
                    </div>
                    <div className="class-create-row">
                        <input
                            type="text"
                            placeholder="开课代码（可选）"
                            value={classForm.offering_code}
                            onChange={(e) => setClassForm((prev) => ({ ...prev, offering_code: e.target.value }))}
                        />
                    </div>
                    <div className="course-code-tip">
                        创建班级后，系统会自动生成课程码。
                    </div>
                    <div className="user-modal-actions">
                        <button onClick={() => setShowCreateClassModal(false)} disabled={creatingClass}>取消</button>
                        <button onClick={handleCreateClass} disabled={creatingClass}>
                            {creatingClass ? '创建中...' : '创建班级'}
                        </button>
                    </div>
                </div>
            </div>
        ) : null}

        {qrModal.open ? (
            <div className="user-modal-overlay" onClick={() => setQrModal({ open: false, item: null })}>
                <div className="user-modal qr-modal" onClick={(e) => e.stopPropagation()}>
                    <h3>{`班级二维码：${qrModal.item?.className || '-'}`}</h3>
                    <div className="qr-modal-code">{`课程码：${qrModal.item?.joinCode || '-'}`}</div>
                    {getJoinUrl(qrModal.item?.joinCode) ? (
                        <div className="qr-modal-body">
                            <QRCodeCanvas value={getJoinUrl(qrModal.item?.joinCode)} size={220} includeMargin />
                            <div className="qr-modal-url">{getJoinUrl(qrModal.item?.joinCode)}</div>
                        </div>
                    ) : (
                        <div className="user-placeholder">当前班级暂无可用课程码。</div>
                    )}
                    <div className="user-modal-actions">
                        <button onClick={() => handleCopyJoinCode(qrModal.item?.joinCode)}>复制课程码</button>
                        <button onClick={() => setQrModal({ open: false, item: null })}>关闭</button>
                    </div>
                </div>
            </div>
        ) : null}
    </div>
);
}

export default TeacherUserManagement;

