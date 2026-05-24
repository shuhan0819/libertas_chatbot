import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Typography, CircularProgress, Button, TextField, Alert } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import axios from 'axios';

export default function Verify() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('');
  const [showResend, setShowResend] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [resendMsg, setResendMsg] = useState('');
  const [resending, setResending] = useState(false);

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) { setStatus('error'); setMessage('無效的驗證連結'); return; }
    axios.get(`/api/auth/verify?token=${token}`)
      .then(res => { setStatus('success'); setMessage(res.data.message); })
      .catch(err => {
        setStatus('error');
        setMessage(err.response?.data?.detail || '驗證失敗');
        setShowResend(true);
      });
  }, [searchParams]);

  const handleResend = async () => {
    setResending(true);
    setResendMsg('');
    try {
      const res = await axios.post('/api/auth/resend-verification', { username, password });
      setResendMsg(res.data.message);
      setShowResend(false);
    } catch (err) {
      setResendMsg(err.response?.data?.detail || '寄送失敗，請稍後再試');
    } finally {
      setResending(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%)',
    }}>
      <Box sx={{
        width: 400, bgcolor: 'white', borderRadius: 4, p: 5,
        boxShadow: '0 24px 64px rgba(0,0,0,0.3)', textAlign: 'center',
      }}>
        {status === 'loading' && (
          <>
            <CircularProgress size={60} sx={{ mb: 3, color: '#1a237e' }} />
            <Typography variant="h6">驗證中...</Typography>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircleIcon sx={{ fontSize: 64, color: '#2e7d32', mb: 2 }} />
            <Typography variant="h5" fontWeight={700} color="#2e7d32" gutterBottom>
              驗證成功！
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              你的信箱已完成驗證，現在可以登入了。
            </Typography>
            <Button fullWidth variant="contained" onClick={() => navigate('/login')}
              sx={{ py: 1.5, borderRadius: 2, background: 'linear-gradient(135deg, #1a237e, #1565c0)', fontSize: '1rem', fontWeight: 600 }}>
              前往登入
            </Button>
          </>
        )}
        {status === 'error' && (
          <>
            <ErrorIcon sx={{ fontSize: 64, color: '#d32f2f', mb: 2 }} />
            <Typography variant="h5" fontWeight={700} color="#d32f2f" gutterBottom>
              驗證失敗
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>{message}</Typography>

            {resendMsg && (
              <Alert severity={resendMsg.includes('已重新') ? 'success' : 'error'} sx={{ mb: 2, textAlign: 'left' }}>
                {resendMsg}
              </Alert>
            )}

            {showResend && (
              <Box sx={{ textAlign: 'left', mb: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  輸入你的帳號密碼重新寄送驗證信：
                </Typography>
                <TextField fullWidth label="帳號" value={username}
                  onChange={e => setUsername(e.target.value)} size="small" sx={{ mb: 1.5 }} />
                <TextField fullWidth label="密碼" type="password" value={password}
                  onChange={e => setPassword(e.target.value)} size="small" sx={{ mb: 1.5 }} />
                <Button fullWidth variant="contained" onClick={handleResend} disabled={resending}
                  sx={{ py: 1.2, borderRadius: 2, background: 'linear-gradient(135deg, #1a237e, #1565c0)' }}>
                  {resending ? '寄送中...' : '重新寄送驗證信'}
                </Button>
              </Box>
            )}

            <Button fullWidth variant="outlined" onClick={() => navigate('/login')}
              sx={{ py: 1.5, borderRadius: 2, fontSize: '1rem' }}>
              返回登入
            </Button>
          </>
        )}
      </Box>
    </Box>
  );
}
