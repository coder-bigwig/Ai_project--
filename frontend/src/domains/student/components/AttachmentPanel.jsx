import React, { useState } from 'react';
import axios from 'axios';

function AttachmentPanel({ courseId, apiBaseUrl, text }) {
    const [attachments, setAttachments] = useState([]);
    const [showList, setShowList] = useState(false);

    const loadAttachments = async () => {
        if (showList) {
            setShowList(false);
            return;
        }

        try {
            const response = await axios.get(`${apiBaseUrl}/api/experiments/${courseId}/attachments`);
            setAttachments(response.data || []);
            setShowList(true);
        } catch (error) {
            console.error('Failed to load attachments:', error);
        }
    };

    return (
        <div className="lab-attachment-panel">
            <button type="button" className="lab-attachment-toggle" onClick={loadAttachments}>
                {showList ? text.hideAttachment : text.viewAttachment}
            </button>
            {showList ? (
                <ul className="lab-attachment-list">
                    {attachments.length === 0 ? (
                        <li className="lab-attachment-empty">{text.noAttachment}</li>
                    ) : (
                        attachments.map((att) => (
                            <li key={att.id}>
                                <span>{att.filename}</span>
                                <button
                                    type="button"
                                    onClick={() => window.open(`${apiBaseUrl}/api/attachments/${att.id}/download-word`, '_blank')}
                                >
                                    {text.download}
                                </button>
                            </li>
                        ))
                    )}
                </ul>
            ) : null}
        </div>
    );
}

export default AttachmentPanel;
