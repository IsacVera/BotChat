<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Welcome Back</h1>
      
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="identifier">Username or Email</label>
          <input
            id="identifier"
            v-model="formData.identifier"
            type="text"
            placeholder="Enter your username or email"
            required
            autofocus
          />
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="formData.password"
            type="password"
            placeholder="Enter your password"
            required
          />
        </div>

        <button type="submit" class="login-button" :disabled="loading">
          {{ loading ? 'Logging in...' : 'Login' }}
        </button>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>
      </form>

      <p class="signup-link">
        Don't have an account? <router-link to="/signup">Sign up</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { apiBase } from '@/lib/apiBase';

const router = useRouter();

const formData = ref({
  identifier: '',
  password: ''
});

const loading = ref(false);
const error = ref('');

async function handleLogin() {
  error.value = '';
  loading.value = true;
  
  try {
    const response = await axios.post(`${apiBase}/users/login/`, {
      identifier: formData.value.identifier,
      password: formData.value.password
    });

    // Store user data (you can use localStorage or a state management library)
    localStorage.setItem('user', JSON.stringify(response.data));
    
    // Redirect to dashboard
    router.push('/');

  } catch (err: any) {
    console.error(err);
    if (err.response?.data?.error) {
      error.value = err.response.data.error;
    } else {
      error.value = 'Login failed. Please check your credentials and try again.';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
@import '../../styles/variables';

.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $color-bg-primary;
  padding: $spacing-lg;
}

.login-card {
  background: $color-bg-secondary;
  border-radius: $radius-md;
  padding: $spacing-3xl;
  width: 100%;
  max-width: 450px;
  box-shadow: $shadow-default;

  h1 {
    color: $color-brand-primary;
    font-size: $font-size-xl;
    font-weight: $font-weight-semibold;
    text-align: center;
    margin-bottom: $spacing-2xl;
  }
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: $spacing-xs;

  label {
    color: $color-text-primary;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
  }

  input {
    background: $color-bg-tertiary;
    border: 1px solid $color-border-default;
    border-radius: $radius-sm;
    padding: 14px $spacing-md;
    color: $color-text-primary;
    font-size: $font-size-base;
    transition: $transition-default;

    &::placeholder {
      color: $color-text-muted;
    }

    &:focus {
      outline: none;
      border-color: $color-border-focus;
      background: $color-bg-hover;
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }
}

.login-button {
  background: $color-brand-secondary;
  color: white;
  border: none;
  border-radius: $radius-sm;
  padding: 14px;
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  cursor: pointer;
  transition: $transition-default;
  margin-top: $spacing-xs;

  &:hover:not(:disabled) {
    background: $color-brand-secondary-hover;
    transform: translateY(-1px);
  }

  &:active:not(:disabled) {
    transform: translateY(0);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.error-message {
  background: $color-error-bg;
  border: 1px solid $color-error-border;
  color: $color-error-text;
  padding: $spacing-sm $spacing-md;
  border-radius: $radius-sm;
  font-size: $font-size-sm;
  text-align: center;
}

.signup-link {
  text-align: center;
  margin-top: $spacing-xl;
  color: $color-text-secondary;
  font-size: $font-size-sm;

  a {
    color: $color-brand-primary;
    text-decoration: none;
    font-weight: $font-weight-semibold;
    transition: $transition-default;

    &:hover {
      color: $color-brand-hover;
      text-decoration: underline;
    }
  }
}
</style>