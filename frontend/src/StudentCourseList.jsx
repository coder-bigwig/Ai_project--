import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import ResourcePreviewContent from './ResourcePreviewContent';
import { persistJupyterTokenFromUrl } from './jupyterAuth';
import cover01 from './assets/system-covers/cover-01.svg';
import cover02 from './assets/system-covers/cover-02.svg';
import cover03 from './assets/system-covers/cover-03.svg';
import './StudentCourseList.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';
const SELECTED_COURSE_CACHE_KEY = 'studentSelectedCourseKey';
const JUPYTERHUB_URL = process.env.REACT_APP_JUPYTERHUB_URL || '';
const DEFAULT_JUPYTERHUB_URL = `${window.location.origin}/jupyter/hub/home`;
const DEFAULT_JUPYTERHUB_HEALTH_URL = `${window.location.origin}/jupyter/hub/health`;
const LEGACY_JUPYTERHUB_URL = `${window.location.protocol}//${window.location.hostname}:8003/jupyter/hub/home`;
const SYSTEM_COVERS = [
    { id: 'system-01', label: '\u7cfb\u7edf\u5c01\u9762 1', src: cover01 },
    { id: 'system-02', label: '\u7cfb\u7edf\u5c01\u9762 2', src: cover02 },
    { id: 'system-03', label: '\u7cfb\u7edf\u5c01\u9762 3', src: cover03 },
];

const TEXT = {
    platformTitle: '\u798f\u5dde\u7406\u5de5\u5b66\u9662AI\u7f16\u7a0b\u5b9e\u8df5\u6559\u5b66\u5e73\u53f0',
    platformSubTitle: '\u5b66\u751f\u7aef / AI Programming Practice Teaching Platform',
    logout: '\u9000\u51fa',
    jupyterHub: '\u8fdb\u5165 JupyterHub',
    studentAccountPrefix: '\u5b66\u751f\u8d26\u53f7\uff1a',
    studentRoleLabel: '\u89d2\u8272\uff1a\u5b66\u751f',
    namePrefix: '\u59d3\u540d',
    classPrefix: '\u73ed\u7ea7',
    studentIdPrefix: '\u5b66\u53f7',
    unknownClass: '\u672a\u7ed1\u5b9a\u73ed\u7ea7',
    moduleLabel: '\u8bfe\u7a0b\u5e93',
    moduleTip: '\u8bfe\u7a0b\u4e0e\u5b9e\u9a8c\u7ba1\u7406',
    resourceModuleLabel: '\u5e73\u53f0\u8d44\u6e90',
    resourceModuleTip: '\u6559\u5b66\u4e0e\u5b9e\u9a8c\u8d44\u6e90',
    profileModuleLabel: '\u4e2a\u4eba\u4e2d\u5fc3',
    profileModuleTip: '\u8d26\u53f7\u4e0e\u5b89\u5168\u8bbe\u7f6e',
    sidebarTitle: '\u6a21\u5757',
    breadcrumbCurrent: '\u8bfe\u7a0b\u5e93',
    resourceBreadcrumbCurrent: '\u6559\u5b66\u4e0e\u5b9e\u9a8c\u8d44\u6e90',
    profileBreadcrumbCurrent: '\u4e2a\u4eba\u4e2d\u5fc3',
    loading: '\u6b63\u5728\u52a0\u8f7d\u8bfe\u7a0b\u5217\u8868...',
    empty: '\u5f53\u524d\u6682\u65e0\u53ef\u7528\u8bfe\u7a0b',
    chooseCourse: '\u8fdb\u5165\u8bfe\u7a0b',
    joinByCodePlaceholder: '\u8f93\u5165\u8bfe\u7a0b\u7801',
    joinByCodeButton: '\u641c\u7d22/\u8f93\u5165\u8bfe\u7a0b\u7801\u52a0\u5165',
    joinCourse: '\u52a0\u5165\u8bfe\u7a0b',
    leaveCourse: '\u9000\u51fa\u8bfe\u7a0b',
    rejoinCourse: '\u91cd\u65b0\u52a0\u5165',
    viewOfferingExperiments: '\u67e5\u770b\u5b9e\u9a8c',
    backToCourseLibrary: '\u8fd4\u56de\u8bfe\u7a0b\u5e93',
    courseCountPrefix: '\u5b9e\u9a8c\u6570\uff1a',
    courseUntitled: '\u672a\u547d\u540d\u8bfe\u7a0b',
    inProgressCountPrefix: '\u8fdb\u884c\u4e2d\uff1a',
    completedCountPrefix: '\u5df2\u5b8c\u6210\uff1a',
    noDescription: '\u6682\u65e0\u63cf\u8ff0',
    teacherPrefix: '\u6388\u8bfe\u8001\u5e08\uff1a',
    unknownTeacher: '\u672a\u77e5',
    openExperiment: '\u6253\u5f00\u5b9e\u9a8c',
    homeSearchPlaceholder: '\u641c\u7d22',
    noSearchResult: '\u672a\u5339\u914d\u5230\u8bfe\u7a0b',
    detailResources: '\u8d44\u6599',
    detailAssignments: '\u4f5c\u4e1a',
    assignmentSearchPlaceholder: '\u641c\u7d22\u4f5c\u4e1a',
    assignmentCountPrefix: '\u4f5c\u4e1a\u6570\uff1a',
    resourceSearchPlaceholderInCourse: '\u641c\u7d22\u8d44\u6599',
    resourceCountPrefixInCourse: '\u8d44\u6599\u9879\uff1a',
    noResourcesInCourse: '\u5f53\u524d\u8bfe\u7a0b\u6682\u65e0\u8d44\u6599',
    offeringCodeLabel: '\u73ed\u7ea7\u5f00\u8bfe\u6807\u8bc6',
    courseCodeLabel: '\u8bfe\u7a0b\u7801',
    detailMenuBack: '\u8fd4\u56de\u8bfe\u7a0b\u5e93',
    detailMenuPortal: '\u8bfe\u7a0b\u95e8\u6237',
    studentCoverMark: '\u5b66',
    noAssignments: '\u5f53\u524d\u8bfe\u7a0b\u6682\u65e0\u4f5c\u4e1a',
    joinCodeMetaPrefix: '\u8bfe\u7a0b\u7801\uff1a',
    uploadPdf: '\u5b9e\u9a8c\u62a5\u544a PDF\uff08\u53ef\u9009\uff09',
    submitHomework: '\u63d0\u4ea4\u4f5c\u4e1a',
    confirmSubmit: '\u786e\u8ba4\u63d0\u4ea4\u5b9e\u9a8c\u5417\uff1f\u63d0\u4ea4\u524d\u8bf7\u5148\u5728 JupyterLab \u4fdd\u5b58\u597d\u6587\u4ef6\u3002',
    submitSuccess: '\u5b9e\u9a8c\u63d0\u4ea4\u6210\u529f\u3002',
    submitSuccessWithPdf: '\u5b9e\u9a8c\u548c PDF \u62a5\u544a\u5df2\u63d0\u4ea4\u3002',
    loadError: '\u52a0\u8f7d\u5b9e\u9a8c\u5217\u8868\u5931\u8d25\uff0c\u8bf7\u5237\u65b0\u91cd\u8bd5\u3002',
    startError: '\u542f\u52a8\u5b9e\u9a8c\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u3002',
    submitErrorPrefix: '\u63d0\u4ea4\u5931\u8d25: ',
    scorePrefix: '\u5f97\u5206\uff1a',
    viewAttachment: '\u67e5\u770b\u9644\u4ef6',
    hideAttachment: '\u9690\u85cf\u9644\u4ef6',
    noAttachment: '\u6682\u65e0\u9644\u4ef6',
    download: '\u4e0b\u8f7d',
    resourceNamePlaceholder: '\u8bf7\u8f93\u5165\u540d\u79f0',
    resourceTypePlaceholder: '\u8bf7\u9009\u62e9\u7c7b\u578b',
    resourceSearch: '\u641c\u7d22',
    resourceTotalPrefix: '\u5e73\u53f0\u8d44\u6e90\u6587\u4ef6\u5171',
    resourceTotalSuffix: '\u4e2a',
    resourceLoading: '\u6b63\u5728\u52a0\u8f7d\u8d44\u6e90\u5217\u8868...',
    resourceEmpty: '\u6682\u65e0\u53ef\u7528\u8d44\u6e90',
    resourceLoadError: '\u52a0\u8f7d\u8d44\u6e90\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002',
    resourceDetailError: '\u52a0\u8f7d\u8d44\u6e90\u8be6\u60c5\u5931\u8d25',
    resourceFileName: '\u6587\u4ef6\u540d',
    resourceFileType: '\u7c7b\u578b',
    resourceCreatedAt: '\u521b\u5efa\u65f6\u95f4',
    operation: '\u64cd\u4f5c',
    detail: '\u8be6\u60c5',
    close: '\u5173\u95ed',
    unsupportedPreview: '\u5f53\u524d\u6587\u4ef6\u7c7b\u578b\u4e0d\u652f\u6301\u5728\u7ebf\u9884\u89c8\uff0c\u8bf7\u4e0b\u8f7d\u67e5\u770b\u3002',
    noPreviewContent: '\u6682\u65e0\u53ef\u9884\u89c8\u5185\u5bb9',
    statusNotStarted: '\u672a\u5f00\u59cb',
    statusInProgress: '\u8fdb\u884c\u4e2d',
    statusSubmitted: '\u5df2\u63d0\u4ea4',
    statusGraded: '\u5df2\u8bc4\u5206',
    majorPrefix: '\u4e13\u4e1a',
    admissionYearPrefix: '\u5165\u5b66\u5e74\u4efd',
    profileInfoTitle: '\u4e2a\u4eba\u4fe1\u606f',
    profilePasswordTitle: '\u4fee\u6539\u5bc6\u7801',
    currentPassword: '\u5f53\u524d\u5bc6\u7801',
    newPassword: '\u65b0\u5bc6\u7801',
    confirmPassword: '\u786e\u8ba4\u65b0\u5bc6\u7801',
    passwordLengthHint: '\u5bc6\u7801\u4e0d\u5c11\u4e8e 6 \u4f4d',
    savePassword: '\u786e\u8ba4\u4fee\u6539',
    profileLoadError: '\u52a0\u8f7d\u4e2a\u4eba\u4fe1\u606f\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002',
    profileLoading: '\u6b63\u5728\u52a0\u8f7d\u4e2a\u4eba\u4fe1\u606f...',
    passwordMismatch: '\u4e24\u6b21\u8f93\u5165\u7684\u65b0\u5bc6\u7801\u4e0d\u4e00\u81f4',
    passwordTooShort: '\u65b0\u5bc6\u7801\u957f\u5ea6\u4e0d\u80fd\u5c11\u4e8e 6 \u4f4d',
    passwordChangeSuccess: '\u5bc6\u7801\u4fee\u6539\u6210\u529f',
    passwordChangeErrorPrefix: '\u4fee\u6539\u5bc6\u7801\u5931\u8d25\uff1a',
    profileNotAvailable: '\u6682\u65e0\u4e2a\u4eba\u4fe1\u606f',
    profileSecurityTitle: '\u8d26\u53f7\u4e0e\u5b89\u5168',
    profilePasswordHint: '\u5b9a\u671f\u4fee\u6539\u5bc6\u7801\uff0c\u4fdd\u969c\u8d26\u53f7\u5b89\u5168\u3002',
    securityQuestionTitle: '\u5bc6\u4fdd\u95ee\u9898',
    securityQuestionConfigured: '\u5df2\u8bbe\u7f6e\u5bc6\u4fdd\u95ee\u9898\u3002',
    securityQuestionUnsetHint: '\u8bf7\u8bbe\u7f6e\u5bc6\u4fdd\u95ee\u9898\uff0c\u7528\u4e8e\u627e\u56de\u5bc6\u7801\u3002',
    securityQuestionLabel: '\u5bc6\u4fdd\u95ee\u9898',
    securityQuestionPlaceholder: '\u4f8b\u5982\uff1a\u4f60\u7684\u7b2c\u4e00\u95e8\u8bfe\u7a0b\u540d\u79f0',
    securityAnswerLabel: '\u5bc6\u4fdd\u7b54\u6848',
    securityAnswerPlaceholder: '\u8bf7\u8f93\u5165\u5bc6\u4fdd\u7b54\u6848',
    securityQuestionUpdateHint: '\u4f60\u53ef\u4ee5\u968f\u65f6\u66f4\u65b0\u5bc6\u4fdd\u95ee\u9898\u3002',
    securityQuestionSetHint: '\u73b0\u5728\u8bbe\u7f6e\uff0c\u65b9\u4fbf\u540e\u7eed\u627e\u56de\u5bc6\u7801\u3002',
    securitySaving: '\u4fdd\u5b58\u4e2d...',
    securityUpdateButton: '\u66f4\u65b0\u5bc6\u4fdd\u95ee\u9898',
    securitySaveButton: '\u4fdd\u5b58\u5bc6\u4fdd\u95ee\u9898',
    securityQuestionMinLength: '\u5bc6\u4fdd\u95ee\u9898\u81f3\u5c11 2 \u4e2a\u5b57\u7b26\u3002',
    securityAnswerMinLength: '\u5bc6\u4fdd\u7b54\u6848\u81f3\u5c11 2 \u4e2a\u5b57\u7b26\u3002',
    securitySaveSuccess: '\u5bc6\u4fdd\u95ee\u9898\u4fdd\u5b58\u6210\u529f\u3002',
    securitySaveErrorPrefix: '\u4fdd\u5b58\u5bc6\u4fdd\u95ee\u9898\u5931\u8d25\uff1a'
};

const RESOURCE_TYPE_OPTIONS = [
    { value: '', label: '\u8bf7\u9009\u62e9\u7c7b\u578b' },
    { value: 'pdf', label: 'pdf' },
    { value: 'doc', label: 'doc' },
    { value: 'docx', label: 'docx' },
    { value: 'xls', label: 'xls' },
    { value: 'xlsx', label: 'xlsx' },
    { value: 'md', label: 'md' },
    { value: 'txt', label: 'txt' }
];

function formatDateTime(value) {
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

function buildCourseKeywordText(course) {
    const title = String(course?.title || '').toLowerCase();
    const description = String(course?.description || '').toLowerCase();
    const tags = Array.isArray(course?.tags) ? course.tags.join(' ').toLowerCase() : '';
    return `${title} ${description} ${tags}`;
}

function getCourseIconMeta(course) {
    const text = buildCourseKeywordText(course);

    if (text.includes('vision') || text.includes('autodrive') || text.includes('\u81ea\u52a8\u9a7e\u9a76') || text.includes('\u89c6\u89c9')) {
        return { label: 'CV', themeClass: 'theme-vision' };
    }
    if (text.includes('matplotlib') || text.includes('\u53ef\u89c6\u5316') || text.includes('\u56fe\u8868')) {
        return { label: 'PLT', themeClass: 'theme-plot' };
    }
    if (text.includes('pandas')) {
        return { label: 'PD', themeClass: 'theme-pandas' };
    }
    if (text.includes('numpy')) {
        return { label: 'NP', themeClass: 'theme-numpy' };
    }
    if (text.includes('scikit') || text.includes('machine learning') || text.includes('\u673a\u5668\u5b66\u4e60')) {
        return { label: 'ML', themeClass: 'theme-ml' };
    }
    if (text.includes('python')) {
        return { label: 'PY', themeClass: 'theme-python' };
    }
    return { label: 'LAB', themeClass: 'theme-generic' };
}

function hashString(value) {
    const text = String(value || '');
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

function resolveCourseCover(item) {
    const seed = String(
        item?.offeringId
        || item?.offeringCode
        || item?.joinCode
        || item?.templateCourseId
        || item?.courseName
        || ''
    ).trim();
    const index = hashString(seed || 'student-cover-seed') % SYSTEM_COVERS.length;
    return SYSTEM_COVERS[index];
}

function progressStatusKey(status) {
    const value = String(status || '').trim().toLowerCase();
    if (!value) return 'not-started';
    if (value.includes('\u8bc4\u5206') || value.includes('graded')) return 'graded';
    if (value.includes('\u63d0\u4ea4') || value.includes('submit')) return 'submitted';
    if (value.includes('\u8fdb\u884c') || value.includes('progress') || value.includes('started')) return 'in-progress';
    return 'not-started';
}

function formatStatusLabel(status) {
    const key = progressStatusKey(status);
    if (key === 'graded') return TEXT.statusGraded;
    if (key === 'submitted') return TEXT.statusSubmitted;
    if (key === 'in-progress') return TEXT.statusInProgress;
    return TEXT.statusNotStarted;
}

function StudentCourseList({ username, onLogout }) {
    const navigate = useNavigate();
    const [coursesWithStatus, setCoursesWithStatus] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadingOfferingExperiments, setLoadingOfferingExperiments] = useState(false);
    const [activeModule, setActiveModule] = useState('courses');
    const [selectedCourseKey, setSelectedCourseKey] = useState(
        () => sessionStorage.getItem(SELECTED_COURSE_CACHE_KEY) || ''
    );
    const [offeringExperiments, setOfferingExperiments] = useState([]);
    const [joinByCode, setJoinByCode] = useState('');
    const [homeKeyword, setHomeKeyword] = useState('');
    const [detailMenu, setDetailMenu] = useState('assignments');
    const [assignmentKeyword, setAssignmentKeyword] = useState('');
    const [profile, setProfile] = useState(() => ({
        real_name: localStorage.getItem('real_name') || '',
        class_name: localStorage.getItem('class_name') || '',
        student_id: localStorage.getItem('student_id') || username || '',
        major: localStorage.getItem('major') || '',
        admission_year: localStorage.getItem('admission_year') || ''
    }));
    const realName = profile.real_name || username || '';
    const studentId = profile.student_id || username || '';
    const moduleLabel = activeModule === 'courses' ? TEXT.moduleLabel : TEXT.profileModuleLabel;
    const breadcrumbLabel = activeModule === 'courses' ? TEXT.breadcrumbCurrent : TEXT.profileBreadcrumbCurrent;

    useEffect(() => {
        loadCoursesWithStatus();
        loadStudentProfileIfNeeded();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const groupedCourses = useMemo(() => {
        const rows = Array.isArray(coursesWithStatus) ? coursesWithStatus : [];
        return rows
            .map((item) => ({
                key: String(item?.offering_id || ''),
                offeringId: String(item?.offering_id || ''),
                offeringCode: String(item?.offering_code || '').trim(),
                joinCode: String(item?.join_code || '').trim(),
                term: String(item?.term || '').trim(),
                major: String(item?.major || '').trim(),
                className: String(item?.class_name || '').trim(),
                offeringStatus: String(item?.status || 'active').trim(),
                memberStatus: String(item?.member_status || '').trim() || 'active',
                memberRole: String(item?.member_role || '').trim(),
                templateCourseId: String(item?.template_course_id || '').trim(),
                courseName: String(item?.template_course_name || '').trim() || TEXT.courseUntitled,
                description: String(item?.template_course_description || '').trim(),
                teacherName: String(item?.created_by || '').trim() || TEXT.unknownTeacher,
                raw: item,
            }))
            .filter((item) => item.offeringId)
            .sort((a, b) => String(a.joinCode || a.offeringCode || '').localeCompare(String(b.joinCode || b.offeringCode || ''), 'zh-Hans-CN'));
    }, [coursesWithStatus]);

    const selectedCourse = useMemo(
        () => groupedCourses.find((item) => item.key === selectedCourseKey) || null,
        [groupedCourses, selectedCourseKey]
    );

    const selectedCourseExperiments = offeringExperiments;
    const filteredGroupedCourses = useMemo(() => {
        const needle = String(homeKeyword || '').trim().toLowerCase();
        if (!needle) return groupedCourses;
        return groupedCourses.filter((item) => {
            const text = [
                item.courseName,
                item.description,
                item.teacherName,
                item.className,
                item.joinCode,
                item.offeringCode,
            ].join(' ').toLowerCase();
            return text.includes(needle);
        });
    }, [groupedCourses, homeKeyword]);

    const filteredSelectedCourseExperiments = useMemo(() => {
        const rows = Array.isArray(selectedCourseExperiments) ? selectedCourseExperiments : [];
        const needle = String(assignmentKeyword || '').trim().toLowerCase();
        if (!needle) return rows;
        return rows.filter((item) => {
            const text = [
                item?.title,
                item?.description,
                Array.isArray(item?.tags) ? item.tags.join(' ') : '',
            ].join(' ').toLowerCase();
            return text.includes(needle);
        });
    }, [assignmentKeyword, selectedCourseExperiments]);

    useEffect(() => {
        if (!selectedCourse?.offeringId) {
            return;
        }
        loadOfferingExperiments(selectedCourse.offeringId);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedCourse?.offeringId]);

    useEffect(() => {
        if (selectedCourseKey) {
            sessionStorage.setItem(SELECTED_COURSE_CACHE_KEY, selectedCourseKey);
            return;
        }
        sessionStorage.removeItem(SELECTED_COURSE_CACHE_KEY);
    }, [selectedCourseKey]);

    const loadCoursesWithStatus = async () => {
        setLoading(true);
        try {
            const response = await axios.get(
                `${API_BASE_URL}/api/student/offerings?student_id=${username}`
            );
            setCoursesWithStatus(response.data || []);
        } catch (error) {
            console.error('Failed to load courses:', error);
            alert(TEXT.loadError);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!selectedCourseKey) {
            setOfferingExperiments([]);
            return;
        }
        if (!groupedCourses.some((item) => item.key === selectedCourseKey)) {
            setSelectedCourseKey('');
            setOfferingExperiments([]);
            sessionStorage.removeItem(SELECTED_COURSE_CACHE_KEY);
        }
    }, [groupedCourses, selectedCourseKey]);

    useEffect(() => {
        if (!selectedCourseKey) {
            setDetailMenu('assignments');
            setAssignmentKeyword('');
            return;
        }
        setDetailMenu('assignments');
        setAssignmentKeyword('');
    }, [selectedCourseKey]);

    const loadOfferingExperiments = async (offeringId) => {
        const normalized = String(offeringId || '').trim();
        if (!normalized) {
            setOfferingExperiments([]);
            return;
        }
        setLoadingOfferingExperiments(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/student/offerings/${normalized}/experiments`, {
                params: { student_id: username }
            });
            setOfferingExperiments(Array.isArray(response.data) ? response.data : []);
        } catch (error) {
            console.error('Failed to load offering experiments:', error);
            setOfferingExperiments([]);
            alert(error.response?.data?.detail || TEXT.loadError);
        } finally {
            setLoadingOfferingExperiments(false);
        }
    };

    const openOffering = (offeringId) => {
        setSelectedCourseKey(offeringId);
        setDetailMenu('assignments');
        setAssignmentKeyword('');
    };

    const handleJoinByCode = async () => {
        const joinCode = String(joinByCode || '').trim();
        if (!joinCode) {
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/api/student/join-by-code`, {
                student_id: username,
                join_code: joinCode
            });
            setJoinByCode('');
            await loadCoursesWithStatus();
        } catch (error) {
            alert(error.response?.data?.detail || TEXT.loadError);
        }
    };

    const handleLeaveOffering = async (offeringId) => {
        try {
            await axios.post(`${API_BASE_URL}/api/student/offerings/${offeringId}/leave`, {
                student_id: username
            });
            if (selectedCourseKey === offeringId) {
                setSelectedCourseKey('');
                setOfferingExperiments([]);
            }
            await loadCoursesWithStatus();
        } catch (error) {
            alert(error.response?.data?.detail || TEXT.loadError);
        }
    };

    const loadStudentProfileIfNeeded = async () => {
        if (!username) {
            return;
        }
        if (profile.real_name && profile.class_name && profile.major && profile.admission_year) {
            return;
        }
        try {
            const response = await axios.get(
                `${API_BASE_URL}/api/student/profile?student_id=${username}`
            );
            const data = response.data || {};
            const nextProfile = {
                real_name: data.real_name || '',
                class_name: data.class_name || '',
                student_id: data.student_id || username,
                major: data.major || data.organization || '',
                admission_year: data.admission_year || ''
            };
            setProfile(nextProfile);
            if (nextProfile.real_name) {
                localStorage.setItem('real_name', nextProfile.real_name);
            }
            if (nextProfile.class_name) {
                localStorage.setItem('class_name', nextProfile.class_name);
            }
            if (nextProfile.student_id) {
                localStorage.setItem('student_id', nextProfile.student_id);
            }
            if (nextProfile.major) {
                localStorage.setItem('major', nextProfile.major);
            }
            if (nextProfile.admission_year) {
                localStorage.setItem('admission_year', nextProfile.admission_year);
            }
        } catch (error) {
            console.error('Failed to load student profile:', error);
        }
    };

    const startOrContinueCourse = async (experiment) => {
        try {
            const experimentId = String(experiment?.id || '').trim();
            if (!experimentId) {
                return;
            }
            await axios.post(
                `${API_BASE_URL}/api/student-experiments/start/${experimentId}?student_id=${username}`
            ).catch(() => null);
            navigate(`/workspace/${experimentId}`);
        } catch (error) {
            console.error('Failed to start experiment:', error);
            alert(TEXT.startError);
        }
    };

    const handleLogout = () => {
        if (typeof onLogout === 'function') {
            onLogout();
            navigate('/login', { replace: true });
            return;
        }

        [
            'username',
            'userRole',
            'isLoggedIn',
            'real_name',
            'class_name',
            'student_id',
            'organization'
        ].forEach((key) => localStorage.removeItem(key));
        window.location.reload();
    };

    const openJupyterHub = async () => {
        try {
            const resp = await axios.get(`${API_BASE_URL}/api/jupyterhub/auto-login-url`, { params: { username } });
            const autoLoginUrl = resp?.data?.jupyter_url;
            if (autoLoginUrl) {
                const launchUrl = persistJupyterTokenFromUrl(autoLoginUrl);
                window.open(launchUrl, '_blank', 'noopener,noreferrer');
                return;
            }
        } catch (error) {
            // fallback below
        }

        if (JUPYTERHUB_URL) {
            window.open(JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
            return;
        }

        try {
            const resp = await fetch(DEFAULT_JUPYTERHUB_HEALTH_URL, { method: 'GET', credentials: 'omit' });
            if (resp.ok) {
                window.open(DEFAULT_JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
                return;
            }
        } catch (error) {
            // ignore
        }

        window.open(LEGACY_JUPYTERHUB_URL, '_blank', 'noopener,noreferrer');
    };

    const handleProfileUpdated = useCallback((nextProfile) => {
        setProfile((prev) => ({ ...prev, ...nextProfile }));
    }, []);

    const sideMenus = [
        { key: 'assignments', label: TEXT.detailAssignments },
        { key: 'resources', label: TEXT.detailResources },
    ];
    const selectedCourseCover = selectedCourse ? resolveCourseCover(selectedCourse) : null;

    return (
        <div className="lab-page-shell">
            <header className="lab-topbar">
                <div className="lab-brand-block">
                    <div className="lab-brand-text">
                        <h1>{TEXT.platformTitle}</h1>
                        <p>{TEXT.platformSubTitle}</p>
                    </div>
                </div>

                <div className="lab-user-block">
                    <span className="lab-user-avatar">{(realName || username || 'U').slice(0, 1).toUpperCase()}</span>
                    <div className="lab-user-text">
                        <span className="lab-user-name">{`${TEXT.studentAccountPrefix}${username || '-'}`}</span>
                        <span className="lab-user-meta">{`${TEXT.studentRoleLabel}  ${TEXT.studentIdPrefix}\uff1a${studentId || '-'}`}</span>
                    </div>
                    <button type="button" className="lab-jhub-btn" onClick={openJupyterHub}>
                        {TEXT.jupyterHub}
                    </button>
                    <button type="button" className="lab-logout-btn" onClick={handleLogout}>
                        {TEXT.logout}
                    </button>
                </div>
            </header>

            <div className="lab-main-layout">
                <aside className="lab-sidebar">
                    <div className="lab-sidebar-title">{TEXT.sidebarTitle}</div>
                    <button
                        type="button"
                        className={`lab-menu-item ${activeModule === 'courses' ? 'active' : ''}`}
                        onClick={() => setActiveModule('courses')}
                        aria-current={activeModule === 'courses' ? 'page' : undefined}
                    >
                        <span className="lab-menu-icon">
                            <LabModuleIcon />
                        </span>
                        <span className="lab-menu-text"><strong>{TEXT.moduleLabel}</strong><small>{TEXT.moduleTip}</small></span>
                    </button>
                    <button
                        type="button"
                        className={`lab-menu-item ${activeModule === 'profile' ? 'active' : ''}`}
                        onClick={() => setActiveModule('profile')}
                        aria-current={activeModule === 'profile' ? 'page' : undefined}
                    >
                        <span className="lab-menu-icon">
                            <ProfileModuleIcon />
                        </span>
                        <span className="lab-menu-text"><strong>{TEXT.profileModuleLabel}</strong><small>{TEXT.profileModuleTip}</small></span>
                    </button>
                </aside>

                <section className="lab-content-panel">
                    <div className="lab-breadcrumb">
                        {moduleLabel} / <strong>{breadcrumbLabel}</strong>
                    </div>
                    {activeModule === 'courses' ? (
                        <>
                            {loading ? (
                                <div className="lab-loading">{TEXT.loading}</div>
                            ) : (
                                <>
                                    {!selectedCourse ? (
                                        <div className="lab-course-home">
                                            <div className="lab-course-home-toolbar">
                                                <div className="lab-course-home-actions">
                                                    <div className="lab-offering-join-row">
                                                        <input
                                                            type="text"
                                                            placeholder={TEXT.joinByCodePlaceholder}
                                                            value={joinByCode}
                                                            onChange={(event) => setJoinByCode(event.target.value)}
                                                        />
                                                        <button type="button" onClick={handleJoinByCode}>{TEXT.joinByCodeButton}</button>
                                                    </div>
                                                </div>
                                                <div className="lab-course-search-box">
                                                    <input
                                                        type="text"
                                                        placeholder={TEXT.homeSearchPlaceholder}
                                                        value={homeKeyword}
                                                        onChange={(event) => setHomeKeyword(event.target.value)}
                                                    />
                                                </div>
                                            </div>

                                            {filteredGroupedCourses.length === 0 ? (
                                                <div className="lab-empty">{groupedCourses.length === 0 ? TEXT.empty : TEXT.noSearchResult}</div>
                                            ) : (
                                                <div className="lab-course-home-grid">
                                                    {filteredGroupedCourses.map((courseGroup) => {
                                                        const cover = resolveCourseCover(courseGroup);
                                                        const isActiveMember = String(courseGroup.memberStatus || '').toLowerCase() === 'active';
                                                        return (
                                                            <article className="lab-course-home-card" key={courseGroup.key}>
                                                                <div className="lab-course-home-cover" aria-hidden>
                                                                    <img src={cover.src} alt={cover.label} />
                                                                    <span>{TEXT.studentCoverMark}</span>
                                                                </div>
                                                                <strong>{courseGroup.courseName}</strong>
                                                                <span>{courseGroup.teacherName}</span>
                                                                <p className="lab-course-home-meta">{`${TEXT.classPrefix}\uff1a${courseGroup.className || TEXT.unknownClass}`}</p>
                                                                {isActiveMember ? (
                                                                    <div className="lab-course-home-card-actions">
                                                                        <button
                                                                            type="button"
                                                                            className="lab-course-open-btn"
                                                                            onClick={() => openOffering(courseGroup.offeringId)}
                                                                        >
                                                                            {TEXT.viewOfferingExperiments}
                                                                        </button>
                                                                        <button
                                                                            type="button"
                                                                            className="lab-course-leave-btn"
                                                                            onClick={() => handleLeaveOffering(courseGroup.offeringId)}
                                                                        >
                                                                            {TEXT.leaveCourse}
                                                                        </button>
                                                                    </div>
                                                                ) : (
                                                                    <div className="lab-offering-left-tag">{TEXT.rejoinCourse}</div>
                                                                )}
                                                            </article>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div className="lab-course-detail-shell">
                                            <aside className="lab-course-detail-sidebar">
                                                <button
                                                    type="button"
                                                    className="lab-course-detail-cover"
                                                    onClick={() => setSelectedCourseKey('')}
                                                >
                                                    <div className="lab-course-home-cover">
                                                        <img src={selectedCourseCover?.src} alt={selectedCourseCover?.label || 'course-cover'} />
                                                        <span>{TEXT.studentCoverMark}</span>
                                                    </div>
                                                    <div className="lab-course-detail-cover-links">
                                                        <span>{TEXT.detailMenuBack}</span>
                                                        <span>{TEXT.detailMenuPortal}</span>
                                                    </div>
                                                </button>
                                                <div className="lab-course-detail-title">{selectedCourse.courseName}</div>
                                                <div className="lab-course-detail-menu">
                                                    {sideMenus.map((item) => (
                                                        <button
                                                            key={item.key}
                                                            type="button"
                                                            className={detailMenu === item.key ? 'active' : ''}
                                                            onClick={() => setDetailMenu(item.key)}
                                                        >
                                                            <span className="dot" />
                                                            <span>{item.label}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            </aside>
                                            <main className="lab-course-detail-main">
                                                {detailMenu === 'resources' ? (
                                                    <div className="lab-course-pane">
                                                        <StudentResourcePanel
                                                            username={username}
                                                            courseId={selectedCourse?.templateCourseId || ''}
                                                            countPrefix={TEXT.resourceCountPrefixInCourse}
                                                            countSuffix=""
                                                            emptyText={TEXT.noResourcesInCourse}
                                                            searchPlaceholder={TEXT.resourceSearchPlaceholderInCourse}
                                                        />
                                                    </div>
                                                ) : (
                                                    <div className="lab-course-pane">
                                                        <div className="lab-course-pane-toolbar">
                                                            <div className="lab-course-home-actions">
                                                                <span className="lab-course-summary">{`${TEXT.assignmentCountPrefix}${selectedCourseExperiments.length}`}</span>
                                                            </div>
                                                            <div className="lab-course-search-box">
                                                                <input
                                                                    type="text"
                                                                    placeholder={TEXT.assignmentSearchPlaceholder}
                                                                    value={assignmentKeyword}
                                                                    onChange={(event) => setAssignmentKeyword(event.target.value)}
                                                                />
                                                            </div>
                                                        </div>
                                                        {loadingOfferingExperiments ? (
                                                            <div className="lab-loading">{TEXT.loading}</div>
                                                        ) : filteredSelectedCourseExperiments.length === 0 ? (
                                                            <div className="lab-empty">
                                                                {selectedCourseExperiments.length === 0 ? TEXT.noAssignments : TEXT.noSearchResult}
                                                            </div>
                                                        ) : (
                                                            <div className="lab-card-grid">
                                                                {filteredSelectedCourseExperiments.map((item) => {
                                                                    const iconMeta = getCourseIconMeta(item);
                                                                    const statusKey = progressStatusKey(item?.status);
                                                                    const numericScore = Number(item?.score);
                                                                    const hasScore = Number.isFinite(numericScore);
                                                                    return (
                                                                        <article className="lab-course-card" key={item.id}>
                                                                            <div className={`lab-course-logo ${iconMeta.themeClass}`} aria-hidden>
                                                                                <span>{iconMeta.label}</span>
                                                                            </div>
                                                                            <h3>{item.title}</h3>
                                                                            <p className="lab-course-desc">{item.description || TEXT.noDescription}</p>
                                                                            <p className="lab-course-teacher">
                                                                                {`${TEXT.teacherPrefix}${String(item?.created_by || '').trim() || selectedCourse.teacherName || TEXT.unknownTeacher}`}
                                                                            </p>
                                                                            <span className={`lab-status-badge status-${statusKey}`}>{formatStatusLabel(item?.status)}</span>
                                                                            {hasScore ? (
                                                                                <span className="lab-score-box">{`${TEXT.scorePrefix}${numericScore}`}</span>
                                                                            ) : null}
                                                                            <div className="lab-chip-row">
                                                                                {(item.tags || []).map((tag) => (
                                                                                    <span key={`${item.id}-${tag}`} className="lab-chip">{tag}</span>
                                                                                ))}
                                                                            </div>
                                                                            <AttachmentPanel courseId={item.id} />
                                                                            <button
                                                                                type="button"
                                                                                className="lab-open-btn"
                                                                                onClick={() => startOrContinueCourse(item)}
                                                                            >
                                                                                {TEXT.openExperiment}
                                                                            </button>
                                                                        </article>
                                                                    );
                                                                })}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </main>
                                        </div>
                                    )}
                                </>
                            )}
                        </>
                    ) : (
                        <StudentProfilePanel
                            username={username}
                            profile={profile}
                            onProfileUpdated={handleProfileUpdated}
                        />
                    )}
                </section>
            </div>
        </div>
    );
}

function AttachmentPanel({ courseId }) {
    const [attachments, setAttachments] = useState([]);
    const [showList, setShowList] = useState(false);

    const loadAttachments = async () => {
        if (showList) {
            setShowList(false);
            return;
        }

        try {
            const response = await axios.get(`${API_BASE_URL}/api/experiments/${courseId}/attachments`);
            setAttachments(response.data || []);
            setShowList(true);
        } catch (error) {
            console.error('Failed to load attachments:', error);
        }
    };

    return (
        <div className="lab-attachment-panel">
            <button type="button" className="lab-attachment-toggle" onClick={loadAttachments}>
                {showList ? TEXT.hideAttachment : TEXT.viewAttachment}
            </button>
            {showList ? (
                <ul className="lab-attachment-list">
                    {attachments.length === 0 ? (
                        <li className="lab-attachment-empty">{TEXT.noAttachment}</li>
                    ) : (
                        attachments.map((att) => (
                            <li key={att.id}>
                                <span>{att.filename}</span>
                                <button
                                    type="button"
                                    onClick={() => window.open(`${API_BASE_URL}/api/attachments/${att.id}/download-word`, '_blank')}
                                >
                                    {TEXT.download}
                                </button>
                            </li>
                        ))
                    )}
                </ul>
            ) : null}
        </div>
    );
}

function StudentResourcePanel({
    username,
    courseId = '',
    offeringId = '',
    countPrefix = TEXT.resourceTotalPrefix,
    countSuffix = TEXT.resourceTotalSuffix,
    emptyText = TEXT.resourceEmpty,
    searchPlaceholder = TEXT.resourceNamePlaceholder,
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

    const scopeQueryString = useMemo(() => buildQueryString(scopeParams), [scopeParams]);

    const loadResources = async ({ name = searchName, fileType = searchType } = {}) => {
        if (!username || (!courseId && !offeringId)) {
            setResources([]);
            setTotalCount(0);
            return;
        }

        setResourceLoading(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/student/resources`, {
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
            alert(TEXT.resourceLoadError);
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
            const response = await axios.get(`${API_BASE_URL}/api/student/resources/${resourceId}`, {
                params: scopeParams
            });
            setDetailData(response.data || null);
        } catch (error) {
            console.error('Failed to load resource detail:', error);
            alert(error.response?.data?.detail || TEXT.resourceDetailError);
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
                        {RESOURCE_TYPE_OPTIONS.map((item) => (
                            <option key={item.value || 'all'} value={item.value}>
                                {item.label}
                            </option>
                        ))}
                    </select>
                    <button type="button" onClick={() => loadResources()}>
                        {TEXT.resourceSearch}
                    </button>
                </div>
                <span className="lab-resource-total">{`${countPrefix}${totalCount}${countSuffix}`}</span>
            </div>

            <div className="lab-resource-table-wrap">
                <table className="lab-resource-table">
                    <thead>
                        <tr>
                            <th>{TEXT.resourceFileName}</th>
                            <th>{TEXT.resourceFileType}</th>
                            <th>{TEXT.resourceCreatedAt}</th>
                            <th>{TEXT.operation}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {resourceLoading ? (
                            <tr>
                                <td colSpan="4" className="lab-resource-empty-row">{TEXT.resourceLoading}</td>
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
                                            {TEXT.detail}
                                        </button>
                                        <button
                                            type="button"
                                            className="lab-resource-link download"
                                            onClick={() => window.open(`${API_BASE_URL}/api/student/resources/${resource.id}/download?${scopeQueryString}`, '_blank')}
                                        >
                                            {TEXT.download}
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
                            <h3>{detailData?.filename || TEXT.detail}</h3>
                            <button type="button" onClick={() => setDetailVisible(false)}>{TEXT.close}</button>
                        </div>
                        <div className="lab-resource-modal-body">
                            {detailLoading ? (
                                <div className="lab-resource-preview-empty">{TEXT.resourceLoading}</div>
                            ) : (
                                <ResourcePreviewContent
                                    detailData={detailData}
                                    accessQueryKey="student_id"
                                    accessQueryValue={username}
                                    accessQueryParams={scopeParams}
                                    loadingText={TEXT.resourceLoading}
                                    emptyText={TEXT.noPreviewContent}
                                    unsupportedText={TEXT.unsupportedPreview}
                                />
                            )}
                        </div>
                        {detailData ? (
                            <div className="lab-resource-modal-footer">
                                <button
                                    type="button"
                                    className="lab-resource-download-btn"
                                    onClick={() => window.open(`${API_BASE_URL}/api/student/resources/${detailData.id}/download?${scopeQueryString}`, '_blank')}
                                >
                                    {TEXT.download}
                                </button>
                            </div>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </div>
    );
}

function StudentProfilePanel({ username, profile, onProfileUpdated }) {
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [securitySubmitting, setSecuritySubmitting] = useState(false);
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [securityQuestion, setSecurityQuestion] = useState('');
    const [securityAnswer, setSecurityAnswer] = useState('');
    const [securityQuestionSet, setSecurityQuestionSet] = useState(false);

    useEffect(() => {
        let cancelled = false;

        const loadProfile = async () => {
            if (!username) {
                return;
            }
            setLoading(true);
            try {
                const response = await axios.get(
                    `${API_BASE_URL}/api/student/profile?student_id=${username}`
                );
                if (cancelled) {
                    return;
                }
                const data = response.data || {};
                const nextProfile = {
                    real_name: data.real_name || '',
                    class_name: data.class_name || '',
                    student_id: data.student_id || username,
                    major: data.major || data.organization || '',
                    admission_year: data.admission_year || '',
                    admission_year_label: data.admission_year_label || '',
                    security_question: data.security_question || '',
                    security_question_set: Boolean(data.security_question_set)
                };
                if (onProfileUpdated) {
                    onProfileUpdated(nextProfile);
                }
                setSecurityQuestion(nextProfile.security_question || '');
                setSecurityQuestionSet(Boolean(nextProfile.security_question_set));
                localStorage.setItem('real_name', nextProfile.real_name || '');
                localStorage.setItem('class_name', nextProfile.class_name || '');
                localStorage.setItem('student_id', nextProfile.student_id || '');
                localStorage.setItem('major', nextProfile.major || '');
                localStorage.setItem('admission_year', nextProfile.admission_year || '');
            } catch (error) {
                if (!cancelled) {
                    console.error('Failed to load student profile:', error);
                    alert(TEXT.profileLoadError);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        loadProfile();
        return () => {
            cancelled = true;
        };
    }, [onProfileUpdated, username]);

    const handleChangePassword = async (event) => {
        event.preventDefault();
        if (newPassword.length < 6) {
            alert(TEXT.passwordTooShort);
            return;
        }
        if (newPassword !== confirmPassword) {
            alert(TEXT.passwordMismatch);
            return;
        }

        setSubmitting(true);
        try {
            const response = await axios.post(`${API_BASE_URL}/api/student/profile/change-password`, {
                student_id: username,
                old_password: currentPassword,
                new_password: newPassword
            });
            alert(response.data?.message || TEXT.passwordChangeSuccess);
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (error) {
            alert(`${TEXT.passwordChangeErrorPrefix}${error.response?.data?.detail || error.message}`);
        } finally {
            setSubmitting(false);
        }
    };

    const handleSaveSecurityQuestion = async (event) => {
        event.preventDefault();
        const normalizedQuestion = String(securityQuestion || '').trim();
        const normalizedAnswer = String(securityAnswer || '').trim();
        if (normalizedQuestion.length < 2) {
            alert(TEXT.securityQuestionMinLength);
            return;
        }
        if (normalizedAnswer.length < 2) {
            alert(TEXT.securityAnswerMinLength);
            return;
        }

        setSecuritySubmitting(true);
        try {
            const response = await axios.post(`${API_BASE_URL}/api/student/profile/security-question`, {
                student_id: username,
                security_question: normalizedQuestion,
                security_answer: normalizedAnswer
            });
            alert(response.data?.message || TEXT.securitySaveSuccess);
            setSecurityQuestion(normalizedQuestion);
            setSecurityQuestionSet(true);
            setSecurityAnswer('');
        } catch (error) {
            alert(`${TEXT.securitySaveErrorPrefix}${error.response?.data?.detail || error.message}`);
        } finally {
            setSecuritySubmitting(false);
        }
    };

    const majorDisplay = profile?.major || profile?.organization || '-';
    const classDisplay = profile?.class_name || '-';
    const admissionYearDisplay = profile?.admission_year_label || profile?.admission_year || '-';
    const studentIdDisplay = profile?.student_id || username || '-';

    return (
        <div className="lab-profile-panel">
            <div className="lab-profile-card">
                <h3>{TEXT.profileInfoTitle}</h3>
                {loading ? (
                    <div className="lab-profile-loading">{TEXT.profileLoading}</div>
                ) : (
                    <div className="lab-profile-grid">
                        <div className="lab-profile-item">
                            <span>{TEXT.studentIdPrefix}</span>
                            <strong>{studentIdDisplay}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{TEXT.majorPrefix}</span>
                            <strong>{majorDisplay || TEXT.profileNotAvailable}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{TEXT.classPrefix}</span>
                            <strong>{classDisplay || TEXT.profileNotAvailable}</strong>
                        </div>
                        <div className="lab-profile-item">
                            <span>{TEXT.admissionYearPrefix}</span>
                            <strong>{admissionYearDisplay || TEXT.profileNotAvailable}</strong>
                        </div>
                    </div>
                )}
            </div>

            <div className="lab-profile-card lab-profile-card--security">
                <h3>{TEXT.profileSecurityTitle}</h3>
                <div className="lab-security-layout">
                    <section className="lab-security-block">
                        <div className="lab-security-head">
                            <h4>{TEXT.profilePasswordTitle}</h4>
                            <p>{TEXT.profilePasswordHint}</p>
                        </div>
                        <form className="lab-password-form lab-security-form" onSubmit={handleChangePassword}>
                            <label htmlFor="current-password">{TEXT.currentPassword}</label>
                            <input
                                id="current-password"
                                type="password"
                                autoComplete="current-password"
                                value={currentPassword}
                                onChange={(event) => setCurrentPassword(event.target.value)}
                                required
                            />

                            <label htmlFor="new-password">{TEXT.newPassword}</label>
                            <input
                                id="new-password"
                                type="password"
                                autoComplete="new-password"
                                value={newPassword}
                                onChange={(event) => setNewPassword(event.target.value)}
                                minLength={6}
                                required
                            />

                            <label htmlFor="confirm-password">{TEXT.confirmPassword}</label>
                            <input
                                id="confirm-password"
                                type="password"
                                autoComplete="new-password"
                                value={confirmPassword}
                                onChange={(event) => setConfirmPassword(event.target.value)}
                                minLength={6}
                                required
                            />

                            <p className="lab-password-hint">{TEXT.passwordLengthHint}</p>
                            <button type="submit" className="lab-password-btn" disabled={submitting}>
                                {submitting ? `${TEXT.savePassword}...` : TEXT.savePassword}
                            </button>
                        </form>
                    </section>

                    <section className="lab-security-block">
                        <div className="lab-security-head">
                            <h4>{TEXT.securityQuestionTitle}</h4>
                            <p>{securityQuestionSet ? TEXT.securityQuestionConfigured : TEXT.securityQuestionUnsetHint}</p>
                        </div>
                        <form className="lab-password-form lab-security-form lab-security-form--qa" onSubmit={handleSaveSecurityQuestion}>
                            <label htmlFor="security-question">{TEXT.securityQuestionLabel}</label>
                            <input
                                id="security-question"
                                type="text"
                                value={securityQuestion}
                                onChange={(event) => setSecurityQuestion(event.target.value)}
                                placeholder={TEXT.securityQuestionPlaceholder}
                                required
                            />

                            <label htmlFor="security-answer">{TEXT.securityAnswerLabel}</label>
                            <input
                                id="security-answer"
                                type="text"
                                value={securityAnswer}
                                onChange={(event) => setSecurityAnswer(event.target.value)}
                                placeholder={TEXT.securityAnswerPlaceholder}
                                required
                            />

                            <p className="lab-password-hint">
                                {securityQuestionSet
                                    ? TEXT.securityQuestionUpdateHint
                                    : TEXT.securityQuestionSetHint}
                            </p>
                            <button type="submit" className="lab-password-btn" disabled={securitySubmitting}>
                                {securitySubmitting ? TEXT.securitySaving : (securityQuestionSet ? TEXT.securityUpdateButton : TEXT.securitySaveButton)}
                            </button>
                        </form>
                    </section>
                </div>
            </div>
        </div>
    );
}

function LabModuleIcon() {
    return (
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
            <path d="M6.5 5H3.5C2.95 5 2.5 5.45 2.5 6V18C2.5 18.55 2.95 19 3.5 19H20.5C21.05 19 21.5 18.55 21.5 18V6C21.5 5.45 21.05 5 20.5 5H17.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            <path d="M9.2 5V4.2C9.2 3.54 9.74 3 10.4 3H13.6C14.26 3 14.8 3.54 14.8 4.2V5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            <rect x="7.2" y="9" width="9.6" height="8" rx="1.6" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M11.2 12.9H12.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
    );
}

function ProfileModuleIcon() {
    return (
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
            <circle cx="12" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M5.5 18.5C6.6 15.9 9 14.4 12 14.4C15 14.4 17.4 15.9 18.5 18.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            <rect x="3.5" y="3.5" width="17" height="17" rx="2.4" stroke="currentColor" strokeWidth="1.4"/>
        </svg>
    );
}

export default StudentCourseList;
