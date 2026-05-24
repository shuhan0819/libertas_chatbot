import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { createTheme, ThemeProvider, CssBaseline } from '@mui/material';

const theme = createTheme({
  palette: {
    primary: { main: '#1a237e' },
    secondary: { main: '#1565c0' },
  },
  typography: {
    fontFamily: '"Noto Sans TC", "Roboto", sans-serif',
    fontSize: 16,          // 基本字體放大
    body1: { fontSize: '1.1rem' },
    body2: { fontSize: '1rem' },
    h6:    { fontSize: '1.3rem' },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, fontSize: '1rem' },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'medium' },
      styleOverrides: {
        root: { '& input, & textarea': { fontSize: '1.1rem' } },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { padding: '12px' },  // 按鈕點擊範圍更大
      },
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <ThemeProvider theme={theme}>
    <CssBaseline />
    <App />
  </ThemeProvider>
);
