
import React, { useState } from 'react';
import axios from 'axios';

interface RelationshipBulkPanelProps {
    apiKey: string | null;
    onUpdate: () => void;
}

const RelationshipBulkPanel: React.FC<RelationshipBulkPanelProps> = ({ apiKey, onUpdate }) => {
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    const handleBulkAction = async (action: string) => {
        if (!confirm("Are you sure you want to perform this bulk action?")) return;
        
        setLoading(true);
        setMessage(null);
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "";
            const res = await axios.post(`${API_BASE}/api/v2/relationships/bulk-update`, 
                { action },
                { headers: { "X-API-Key": apiKey } }
            );
            setMessage(`Success! Updated ${res.data.updated_count} relationships.`);
            onUpdate(); // Refresh parent
            
            setTimeout(() => setMessage(null), 3000);
        } catch (err: any) {
             setMessage(`Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: '#1e1e1e',
            border: '1px solid #333',
            borderRadius: '8px',
            padding: '15px',
            zIndex: 1000,
            boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
            color: 'white',
            width: '300px'
        }}>
            <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: '600' }}>Bulk Actions</h4>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button 
                    onClick={() => handleBulkAction('enable_safe')}
                    disabled={loading}
                    style={{
                        padding: '8px',
                        background: '#10b981',
                        border: 'none',
                        borderRadius: '4px',
                        color: 'white',
                        cursor: 'pointer',
                        opacity: loading ? 0.7 : 1
                    }}
                >
                    Enable All Safe (Green)
                </button>
                
                <button 
                     onClick={() => handleBulkAction('disable_heuristic')}
                     disabled={loading}
                     style={{
                        padding: '8px',
                        background: '#f59e0b',
                        border: 'none',
                        borderRadius: '4px',
                        color: 'black',
                        cursor: 'pointer',
                        opacity: loading ? 0.7 : 1
                    }}
                >
                    Disable All Heuristic (Yellow)
                </button>
            </div>
            
            {loading && <div style={{ marginTop: '10px', fontSize: '12px' }}>Processing...</div>}
            {message && <div style={{ marginTop: '10px', fontSize: '12px', color: message.startsWith('Error') ? '#ef4444' : '#10b981' }}>{message}</div>}
        </div>
    );
};

export default RelationshipBulkPanel;
