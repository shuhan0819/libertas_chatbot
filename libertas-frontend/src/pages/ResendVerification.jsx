import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function ResendVerification() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async () => {
    setLoading(true);
    setMsg('');
    try {
      const res = await axios.post('/api/auth/resend-verification', { username, password });
      setMsg(res.data.message);
      setIsSuccess(true);
    } catch (err) {
      setMsg(err.response?.data?.detail || '寄送失敗，請稍後再試');
      setIsSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%)',
    }}>
      <Box sx={{ width: 400, bgcolor: 'white', borderRadius: 4, p: 5, boxShadow: '0 24px 64px rgba(0,0,0,0.3)' }}>
        <Typography variant="h5" fontWeight={700} color="#1a237e" sx={{ mb: 1 }}>重新寄送驗證信</Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>輸入你的帳號密碼，我們將重新寄送驗證信到你的 Gmail。</Typography>
        {msg && <Alert severity={isSuccess ? 'success' : 'error'} sx={{ mb: 2 }}>{msg}</Alert>}
        <TextField fullWidth label="帳號" value={username} onChange={e => setUsername(e.target.value)} sx={{ mb: 2 }} />
        <TextField fullWidth label="密碼" type="password" value={password} onChange={e => setPassword(e.target.value)} sx={{ mb: 3 }} />
        <Button fullWidth variant="contained" onClick={handleSubmit} disabled={loading}
          sx={{ py: 1.5, borderRadius: 2, background: 'linear-gradient(135deg, #1a237e, #1565c0)', mb: 2 }}>
          {loading ? '寄送中...' : '重新寄送驗證信'}
        </Button>
        <Button fullWidth variant="text" onClick={() => navigate('/login')}>返回登入</Button>
      </Box>
    </Box>
  );
}
