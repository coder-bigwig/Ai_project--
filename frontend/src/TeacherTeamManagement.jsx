import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import './TeacherTeamManagement.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

function normalizeOfferings(items, courseId) {
    if (!Array.isArray(items)) return [];
    const normalizedCourseId = String(courseId || '').trim();
    return items
        .filter((item) => {
            if (String(item?.template_course_id || '').trim() !== normalizedCourseId) return false;
            const status = String(item?.status || '').trim().toLowerCase();
            return status !== 'archived';
        })
        .map((item) => {
            const className = String(item?.class_name || '').trim();
            if (!className) return null;
            return {
                offeringId: String(item?.offering_id || '').trim(),
                className,
                offeringCode: String(item?.offering_code || '').trim() || '-',
                createdBy: String(item?.created_by || '').trim(),
            };
        })
        .filter((item) => item && item.offeringId);
}

function roleLabel(role, isCreator) {
    if (isCreator) return '创建者';
    const key = String(role || '').trim().toLowerCase();
    if (key === 'teacher') return '教师';
    if (key === 'ta') return '助教';
    if (key === 'admin') return '管理员';
    return role || '-';
}

function formatShortDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';
    return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function roleOrder(label) {
    if (label === '创建者') return 0;
    if (label === '教师') return 1;
    if (label === '助教') return 2;
    if (label === '管理员') return 3;
    return 9;
}

function memberRoleOrder(role) {
    const key = String(role || '').trim().toLowerCase();
    if (key === 'teacher') return 0;
    if (key === 'ta') return 1;
    if (key === 'admin') return 2;
    return 9;
}

function normalizeAssignableRole(role) {
    const key = String(role || '').trim().toLowerCase();
    return key === 'ta' ? 'ta' : 'teacher';
}

function buildCsv(rows) {
    const header = ['姓名', '角色', '学号/工号', '加入时间', '所在班级'];
    const escape = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const body = rows.map((item) => [
        item.name,
        item.roleLabel,
        item.userKey,
        formatShortDate(item.joinAt),
        item.classNames.join('、'),
    ].map(escape).join(','));
    return [header.join(','), ...body].join('\n');
}

function TeacherTeamManagement({ username, courseId = '' }) {
    const normalizedCourseId = String(courseId || '').trim();
    const normalizedCurrentUserKey = String(username || '').trim().toLowerCase();
    const [loading, setLoading] = useState(false);
    const [offerings, setOfferings] = useState([]);
    const [membersByOffering, setMembersByOffering] = useState({});
    const [keyword, setKeyword] = useState('');
    const [selectedKeys, setSelectedKeys] = useState([]);

    const [showAddModal, setShowAddModal] = useState(false);
    const [adding, setAdding] = useState(false);
    const [removing, setRemoving] = useState(false);
    const [newMemberKey, setNewMemberKey] = useState('');
    const [newMemberRole, setNewMemberRole] = useState('teacher');
    const [selectedOfferingIds, setSelectedOfferingIds] = useState([]);
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [assigning, setAssigning] = useState(false);
    const [assignTarget, setAssignTarget] = useState(null);
    const [assignRole, setAssignRole] = useState('teacher');
    const [assignOfferingIds, setAssignOfferingIds] = useState([]);

    const loadTeamData = useCallback(async () => {
        if (!normalizedCourseId) return;
        setLoading(true);
        try {
            const offeringsRes = await axios.get(`${API_BASE_URL}/api/teacher/offerings`, {
                params: { teacher_username: username }
            });
            const normalizedOfferings = normalizeOfferings(offeringsRes.data, normalizedCourseId);
            setOfferings(normalizedOfferings);

            if (normalizedOfferings.length === 0) {
                setMembersByOffering({});
                return;
            }

            const memberResults = await Promise.all(
                normalizedOfferings.map(async (item) => {
                    try {
                        const memberRes = await axios.get(`${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(item.offeringId)}/members`, {
                            params: { teacher_username: username }
                        });
                        return {
                            offeringId: item.offeringId,
                            members: Array.isArray(memberRes.data) ? memberRes.data : [],
                        };
                    } catch (error) {
                        return { offeringId: item.offeringId, members: [] };
                    }
                })
            );

            const nextMap = {};
            memberResults.forEach((item) => {
                nextMap[item.offeringId] = item.members;
            });
            setMembersByOffering(nextMap);
        } catch (error) {
            setOfferings([]);
            setMembersByOffering({});
            alert(error.response?.data?.detail || '加载教师团队失败');
        } finally {
            setLoading(false);
        }
    }, [normalizedCourseId, username]);

    useEffect(() => {
        loadTeamData();
    }, [loadTeamData]);

    useEffect(() => {
        if (!showAddModal && !showAssignModal) return;
        loadTeamData();
    }, [loadTeamData, showAddModal, showAssignModal]);

    useEffect(() => {
        const handleWindowFocus = () => {
            loadTeamData();
        };
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                loadTeamData();
            }
        };

        window.addEventListener('focus', handleWindowFocus);
        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => {
            window.removeEventListener('focus', handleWindowFocus);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [loadTeamData]);

    useEffect(() => {
        const validOfferingIds = new Set(offerings.map((item) => item.offeringId).filter(Boolean));
        setSelectedOfferingIds((prev) => prev.filter((offeringId) => validOfferingIds.has(offeringId)));
        setAssignOfferingIds((prev) => prev.filter((offeringId) => validOfferingIds.has(offeringId)));
    }, [offerings]);

    const teamRows = useMemo(() => {
        const map = new Map();

        offerings.forEach((offering) => {
            const members = Array.isArray(membersByOffering[offering.offeringId]) ? membersByOffering[offering.offeringId] : [];
            members.forEach((member) => {
                const rawRole = String(member?.role || '').trim().toLowerCase();
                const rawStatus = String(member?.status || '').trim().toLowerCase();
                if (!['teacher', 'ta', 'admin'].includes(rawRole)) return;
                if (rawStatus && rawStatus !== 'active' && rawStatus !== 'joined') return;

                const userKey = String(member?.user_key || '').trim();
                if (!userKey) return;

                const id = userKey.toLowerCase();
                const isCreator = Boolean(offering.createdBy) && offering.createdBy.toLowerCase() === id;
                const current = map.get(id);

                if (!current) {
                    map.set(id, {
                        id,
                        name: userKey,
                        userKey,
                        memberRole: rawRole,
                        roleLabel: roleLabel(rawRole, isCreator),
                        joinAt: member?.join_at || null,
                        classNames: new Set([offering.className]),
                        offeringIds: new Set([offering.offeringId]),
                        protectedOfferingIds: new Set(isCreator ? [offering.offeringId] : []),
                    });
                    return;
                }

                current.classNames.add(offering.className);
                current.offeringIds.add(offering.offeringId);
                if (isCreator) {
                    current.protectedOfferingIds.add(offering.offeringId);
                }
                const nextRole = roleLabel(rawRole, isCreator);
                if (roleOrder(nextRole) < roleOrder(current.roleLabel)) {
                    current.roleLabel = nextRole;
                }
                if (memberRoleOrder(rawRole) < memberRoleOrder(current.memberRole)) {
                    current.memberRole = rawRole;
                }
                const currentTime = new Date(current.joinAt || 0).getTime();
                const nextTime = new Date(member?.join_at || 0).getTime();
                if (nextTime > currentTime) {
                    current.joinAt = member?.join_at || current.joinAt;
                }
            });
        });

        return Array.from(map.values())
            .map((item) => ({
                ...item,
                memberRole: normalizeAssignableRole(item.memberRole),
                classNames: Array.from(item.classNames).sort((a, b) => a.localeCompare(b, 'zh-Hans-CN')),
                offeringIds: Array.from(item.offeringIds),
                protectedOfferingIds: Array.from(item.protectedOfferingIds),
            }))
            .sort((a, b) => {
                const roleDiff = roleOrder(a.roleLabel) - roleOrder(b.roleLabel);
                if (roleDiff !== 0) return roleDiff;
                return a.name.localeCompare(b.name, 'zh-Hans-CN');
            });
    }, [membersByOffering, offerings]);

    const filteredRows = useMemo(() => {
        const needle = String(keyword || '').trim().toLowerCase();
        if (!needle) return teamRows;
        return teamRows.filter((item) => {
            const name = String(item.name || '').toLowerCase();
            const userKey = String(item.userKey || '').toLowerCase();
            return name.includes(needle) || userKey.includes(needle);
        });
    }, [keyword, teamRows]);

    useEffect(() => {
        setSelectedKeys((prev) => prev.filter(
            (item) => item !== normalizedCurrentUserKey && filteredRows.some((row) => row.id === item)
        ));
    }, [filteredRows, normalizedCurrentUserKey]);

    const removableFilteredRows = useMemo(
        () => filteredRows.filter((row) => row.id !== normalizedCurrentUserKey),
        [filteredRows, normalizedCurrentUserKey]
    );
    const allChecked = removableFilteredRows.length > 0
        && removableFilteredRows.every((row) => selectedKeys.includes(row.id));

    const toggleAll = () => {
        if (allChecked) {
            setSelectedKeys((prev) => prev.filter((key) => !removableFilteredRows.some((row) => row.id === key)));
            return;
        }
        setSelectedKeys((prev) => {
            const next = new Set(prev);
            removableFilteredRows.forEach((row) => next.add(row.id));
            return Array.from(next);
        });
    };

    const toggleRow = (id) => {
        if (id === normalizedCurrentUserKey) return;
        setSelectedKeys((prev) => {
            if (prev.includes(id)) return prev.filter((item) => item !== id);
            return [...prev, id];
        });
    };

    const handleExport = () => {
        if (filteredRows.length === 0) {
            alert('暂无可导出的教师团队数据');
            return;
        }
        const csv = buildCsv(filteredRows);
        const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'teacher-team.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    };

    const handleAddMember = async () => {
        const userKey = String(newMemberKey || '').trim();
        if (!userKey) {
            alert('请输入成员工号/学号');
            return;
        }
        const targetOfferingIds = selectedOfferingIds.length > 0
            ? selectedOfferingIds
            : (newMemberRole === 'teacher'
                ? offerings.map((item) => item.offeringId).filter(Boolean)
                : []);
        if (targetOfferingIds.length === 0) {
            alert(newMemberRole === 'teacher' ? '当前课程暂无可分配班级' : '请至少选择一个班级');
            return;
        }

        setAdding(true);
        try {
            await Promise.all(
                targetOfferingIds.map((offeringId) => axios.post(`${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(offeringId)}/members`, {
                    teacher_username: username,
                    members: [{ user_key: userKey, role: newMemberRole }],
                }))
            );
            setShowAddModal(false);
            setNewMemberKey('');
            setNewMemberRole('teacher');
            setSelectedOfferingIds([]);
            await loadTeamData();
            alert('成员添加成功');
        } catch (error) {
            alert(error.response?.data?.detail || '添加成员失败');
        } finally {
            setAdding(false);
        }
    };

    const handleRemoveMembers = async () => {
        if (selectedKeys.length === 0) {
            alert('请先勾选要删除的成员');
            return;
        }

        const selectedRows = teamRows.filter(
            (row) => selectedKeys.includes(row.id) && row.id !== normalizedCurrentUserKey
        );
        if (selectedRows.length === 0) {
            alert('未找到可删除的成员（不允许删除自己）');
            return;
        }
        if (!window.confirm(`确认删除已勾选的 ${selectedRows.length} 名成员吗？`)) {
            return;
        }

        const requests = [];
        let skippedCreatorCount = 0;
        selectedRows.forEach((row) => {
            const protectedSet = new Set(row.protectedOfferingIds || []);
            const targetOfferingIds = (row.offeringIds || []).filter((offeringId) => !protectedSet.has(offeringId));
            if (targetOfferingIds.length === 0) {
                skippedCreatorCount += 1;
                return;
            }
            targetOfferingIds.forEach((offeringId) => {
                requests.push(
                    axios.delete(
                        `${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(offeringId)}/members/${encodeURIComponent(row.userKey)}`,
                        { params: { teacher_username: username } }
                    )
                );
            });
        });

        if (requests.length === 0) {
            alert('选中的成员都是班级创建者，无法删除');
            return;
        }

        setRemoving(true);
        try {
            const results = await Promise.allSettled(requests);
            const failed = results.filter((item) => item.status === 'rejected');
            const successCount = results.length - failed.length;
            await loadTeamData();
            setSelectedKeys([]);

            if (failed.length === 0) {
                if (skippedCreatorCount > 0) {
                    alert(`删除完成，已跳过 ${skippedCreatorCount} 名班级创建者`);
                } else {
                    alert('成员删除成功');
                }
                return;
            }

            const detail = failed[0]?.reason?.response?.data?.detail || '部分成员删除失败';
            if (skippedCreatorCount > 0) {
                alert(`已删除 ${successCount} 条成员关系，失败 ${failed.length} 条，跳过 ${skippedCreatorCount} 名班级创建者。${detail}`);
            } else {
                alert(`已删除 ${successCount} 条成员关系，失败 ${failed.length} 条。${detail}`);
            }
        } catch (error) {
            alert(error.response?.data?.detail || '删除成员失败');
        } finally {
            setRemoving(false);
        }
    };

    const toggleOffering = (offeringId) => {
        setSelectedOfferingIds((prev) => {
            if (prev.includes(offeringId)) return prev.filter((item) => item !== offeringId);
            return [...prev, offeringId];
        });
    };

    const closeAssignModal = ({ force = false } = {}) => {
        if (assigning && !force) return;
        setShowAssignModal(false);
        setAssignTarget(null);
        setAssignRole('teacher');
        setAssignOfferingIds([]);
    };

    const openAssignModal = (row) => {
        const target = row || null;
        if (!target) return;
        setAssignTarget(target);
        setAssignRole(normalizeAssignableRole(target.memberRole));
        setAssignOfferingIds(Array.isArray(target.offeringIds) ? target.offeringIds : []);
        setShowAssignModal(true);
    };

    const assignTargetOfferingSet = useMemo(() => new Set(assignTarget?.offeringIds || []), [assignTarget]);
    const assignTargetProtectedOfferingSet = useMemo(
        () => new Set(assignTarget?.protectedOfferingIds || []),
        [assignTarget]
    );

    const toggleAssignOffering = (offeringId) => {
        if (assigning) return;
        if (assignTargetProtectedOfferingSet.has(offeringId)) return;
        setAssignOfferingIds((prev) => {
            if (prev.includes(offeringId)) return prev.filter((item) => item !== offeringId);
            return [...prev, offeringId];
        });
    };

    const handleAssignMemberClasses = async () => {
        if (!assignTarget?.userKey) {
            alert('No member selected');
            return;
        }
        const selectedOfferingSet = new Set(assignOfferingIds.filter(Boolean));
        const toAddOfferingIds = offerings
            .map((item) => item.offeringId)
            .filter((offeringId) => offeringId && selectedOfferingSet.has(offeringId) && !assignTargetOfferingSet.has(offeringId));
        const toRemoveOfferingIds = offerings
            .map((item) => item.offeringId)
            .filter(
                (offeringId) =>
                    offeringId &&
                    !selectedOfferingSet.has(offeringId) &&
                    assignTargetOfferingSet.has(offeringId) &&
                    !assignTargetProtectedOfferingSet.has(offeringId)
            );

        if (toAddOfferingIds.length === 0 && toRemoveOfferingIds.length === 0) {
            alert('No class assignment changes');
            return;
        }

        const userKey = assignTarget.userKey;
        setAssigning(true);
        try {
            const requests = [
                ...toAddOfferingIds.map((offeringId) => ({
                    type: 'add',
                    promise: axios.post(`${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(offeringId)}/members`, {
                        teacher_username: username,
                        members: [{ user_key: userKey, role: assignRole }],
                    }),
                })),
                ...toRemoveOfferingIds.map((offeringId) => ({
                    type: 'remove',
                    promise: axios.delete(
                        `${API_BASE_URL}/api/teacher/offerings/${encodeURIComponent(offeringId)}/members/${encodeURIComponent(userKey)}`,
                        { params: { teacher_username: username } }
                    ),
                })),
            ];
            const results = await Promise.allSettled(requests.map((item) => item.promise));
            const failed = [];
            let addSuccess = 0;
            let removeSuccess = 0;
            results.forEach((item, index) => {
                const request = requests[index];
                if (item.status === 'fulfilled') {
                    if (request.type === 'add') addSuccess += 1;
                    if (request.type === 'remove') removeSuccess += 1;
                    return;
                }
                failed.push(item);
            });

            await loadTeamData();

            if (failed.length === 0) {
                alert(`Updated class assignment for ${userKey}: +${addSuccess}, -${removeSuccess}`);
                closeAssignModal({ force: true });
                return;
            }

            const detail = failed[0]?.reason?.response?.data?.detail || 'Partial class assignment update failed';
            alert(`Updated class assignment for ${userKey}: +${addSuccess}, -${removeSuccess}, failed ${failed.length}. ${detail}`);
            if (addSuccess > 0 || removeSuccess > 0) {
                closeAssignModal({ force: true });
            }
        } catch (error) {
            alert(error.response?.data?.detail || 'Class assignment failed');
        } finally {
            setAssigning(false);
        }
    };

    if (!normalizedCourseId) {
        return <div className="team-empty">未选择课程，无法管理教师团队。</div>;
    }

    return (
        <div className="team-management">
            <div className="team-toolbar">
                <button type="button" className="team-add-btn" onClick={() => setShowAddModal(true)}>
                    添加成员
                </button>
                <div className="team-toolbar-right">
                    <button
                        type="button"
                        className="team-link-btn"
                        onClick={loadTeamData}
                        disabled={loading}
                    >
                        {loading ? '刷新中...' : '刷新班级'}
                    </button>
                    <button
                        type="button"
                        className="team-link-btn danger"
                        onClick={handleRemoveMembers}
                        disabled={removing || loading || selectedKeys.length === 0}
                    >
                        {removing ? '删除中...' : '删除成员'}
                    </button>
                    <button type="button" className="team-link-btn" onClick={handleExport}>
                        导出教师团队
                    </button>
                    <div className="team-search">
                        <input
                            type="text"
                            value={keyword}
                            onChange={(event) => setKeyword(event.target.value)}
                            placeholder="请输入姓名或工号"
                        />
                    </div>
                </div>
            </div>

            <div className="team-head">
                <span>全体教师</span>
                <span>共 {filteredRows.length} 人</span>
            </div>

            <div className="team-table-wrap">
                {loading ? (
                    <div className="team-empty">加载中...</div>
                ) : filteredRows.length === 0 ? (
                    <div className="team-empty">暂无教师团队成员</div>
                ) : (
                    <table className="team-table">
                        <thead>
                            <tr>
                                <th className="checkbox-col">
                                    <input type="checkbox" checked={allChecked} onChange={toggleAll} />
                                </th>
                                <th>姓名</th>
                                <th>角色</th>
                                <th>学号/工号</th>
                                <th>加入时间</th>
                                <th className="action-col">班级分配</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredRows.map((item) => (
                                <tr key={item.id}>
                                    <td>
                                        <input
                                            type="checkbox"
                                            checked={selectedKeys.includes(item.id)}
                                            onChange={() => toggleRow(item.id)}
                                            disabled={item.id === normalizedCurrentUserKey}
                                        />
                                    </td>
                                    <td>{item.name}</td>
                                    <td>{item.roleLabel}</td>
                                    <td>{item.userKey}</td>
                                    <td>{formatShortDate(item.joinAt)}</td>
                                    <td>
                                        <button
                                            type="button"
                                            className="team-inline-btn"
                                            onClick={() => openAssignModal(item)}
                                            disabled={loading || offerings.length === 0}
                                        >
                                            分配
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {showAddModal ? (
                <div className="team-modal-overlay" onClick={() => setShowAddModal(false)}>
                    <div className="team-modal" onClick={(event) => event.stopPropagation()}>
                        <h3>添加成员</h3>
                        <div className="team-modal-row">
                            <label htmlFor="new-member-key">工号/学号</label>
                            <input
                                id="new-member-key"
                                type="text"
                                value={newMemberKey}
                                onChange={(event) => setNewMemberKey(event.target.value)}
                                placeholder="请输入成员账号"
                            />
                        </div>
                        <div className="team-modal-row">
                            <label htmlFor="new-member-role">角色</label>
                            <select
                                id="new-member-role"
                                value={newMemberRole}
                                onChange={(event) => setNewMemberRole(event.target.value)}
                            >
                                <option value="teacher">教师</option>
                                <option value="ta">助教</option>
                            </select>
                        </div>
                        <div className="team-modal-row">
                            <label>分配班级</label>
                            <div className="team-offering-list">
                                {loading ? (
                                    <span className="team-modal-tip">正在同步班级...</span>
                                ) : offerings.length === 0 ? (
                                    <span className="team-modal-tip">当前课程暂无班级</span>
                                ) : (
                                    offerings.map((item) => (
                                        <label key={item.offeringId}>
                                            <input
                                                type="checkbox"
                                                checked={selectedOfferingIds.includes(item.offeringId)}
                                                onChange={() => toggleOffering(item.offeringId)}
                                            />
                                            <span>{item.className} ({item.offeringCode})</span>
                                        </label>
                                    ))
                                )}
                            </div>
                        </div>
                        <div className="team-modal-actions">
                            <button type="button" onClick={() => setShowAddModal(false)} disabled={adding}>取消</button>
                            <button type="button" onClick={handleAddMember} disabled={adding}>
                                {adding ? '添加中...' : '确认添加'}
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}

            {showAssignModal ? (
                <div className="team-modal-overlay" onClick={closeAssignModal}>
                    <div className="team-modal" onClick={(event) => event.stopPropagation()}>
                        <h3>{`班级分配：${assignTarget?.userKey || '-'}`}</h3>
                        <div className="team-modal-row">
                            <label htmlFor="assign-member-role">角色</label>
                            <select
                                id="assign-member-role"
                                value={assignRole}
                                onChange={(event) => setAssignRole(event.target.value)}
                                disabled={assigning}
                            >
                                <option value="teacher">教师</option>
                                <option value="ta">助教</option>
                            </select>
                        </div>
                        <div className="team-modal-row">
                            <label>可分配班级</label>
                            <div className="team-offering-list">
                                {loading ? (
                                    <span className="team-modal-tip">正在同步班级...</span>
                                ) : offerings.length === 0 ? (
                                    <span className="team-modal-tip">当前课程暂无班级</span>
                                ) : (
                                    offerings.map((item) => {
                                        const assigned = assignTargetOfferingSet.has(item.offeringId);
                                        const isProtected = assignTargetProtectedOfferingSet.has(item.offeringId);
                                        const checked = assignOfferingIds.includes(item.offeringId);
                                        return (
                                            <label key={item.offeringId} className={isProtected ? 'is-disabled' : ''}>
                                                <input
                                                    type="checkbox"
                                                    checked={checked}
                                                    onChange={() => toggleAssignOffering(item.offeringId)}
                                                    disabled={isProtected || assigning}
                                                />
                                                <span>{item.className} ({item.offeringCode})</span>
                                                {isProtected ? <em className="team-offering-status">Creator class</em> : (assigned ? <em className="team-offering-status">Assigned</em> : null)}
                                            </label>
                                        );
                                    })
                                )}
                            </div>
                        </div>
                        <div className="team-modal-actions">
                            <button type="button" onClick={closeAssignModal} disabled={assigning}>取消</button>
                            <button type="button" onClick={handleAssignMemberClasses} disabled={assigning}>
                                {assigning ? '分配中...' : '确认分配'}
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </div>
    );
}

export default TeacherTeamManagement;
