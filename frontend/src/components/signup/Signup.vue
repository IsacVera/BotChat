<template>
  <div class="signup-container">
    <div class="signup-card">
      <h1>Sign up</h1>
      
      <form @submit.prevent="handleSignup" class="signup-form">
        <div class="form-group">
          <label for="username">Username</label>
          <input
            id="username"
            v-model="formData.username"
            type="text"
            placeholder="Choose a username"
            required
          />
        </div>

        <div class="form-group">
          <label for="email">Email</label>
          <input
            id="email"
            v-model="formData.email"
            type="email"
            placeholder="Enter your email"
            required
          />
        </div>

        <div class="form-group">
          <label for="companyName">Company Name</label>
          <input
            id="companyName"
            v-model="formData.companyName"
            type="text"
            placeholder="Enter your company name"
            required
          />
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="formData.password"
            type="password"
            placeholder="Create a password"
            required
          />
        </div>

        <div class="form-group">
          <label for="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            v-model="formData.confirmPassword"
            type="password"
            placeholder="Confirm your password"
            required
          />
        </div>

        <button type="submit" class="signup-button" :disabled="loading">
          {{ loading ? 'Creating Account...' : 'Sign up' }}
        </button>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <div v-if="success" class="success-message">
          {{ success }}
        </div>
      </form>

      <p class="login-link">
        Already have an account? <router-link to="/">Login</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const apiBase = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

const formData = ref({
  username: '',
  email: '',
  companyName: '',
  password: '',
  confirmPassword: ''
});

const loading = ref(false);
const error = ref('');
const success = ref('');

async function handleSignup() {
  error.value = '';
  success.value = '';

  // Validation
  if (formData.value.password !== formData.value.confirmPassword) {
    error.value = 'Passwords do not match';
    return;
  }

  if (formData.value.password.length < 8) {
    error.value = 'Password must be at least 8 characters';
    return;
  }

  loading.value = true;
  
  try {
    await axios.post(`${apiBase}/users/signup/`, {
      username: formData.value.username,
      email: formData.value.email,
      password: formData.value.password,
      company_name: formData.value.companyName
    });

    success.value = 'Account created successfully! Redirecting...';
    
    setTimeout(() => {
      router.push('/');
    }, 2000);

  } catch (err: any) {
    console.error(err);
    if (err.response?.data?.error) {
      error.value = err.response.data.error;
    } else if (err.response?.data) {
      // Show validation errors
      const errors = err.response.data;
      const errorMessages = Object.entries(errors)
        .map(([field, msgs]: [string, any]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('; ');
      error.value = errorMessages || 'Signup failed. Please try again.';
    } else {
      error.value = 'Signup failed. Please try again.';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
@import '../../styles/variables';

.signup-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $color-bg-primary;
  padding: $spacing-lg;
}

.signup-card {
  background: $color-bg-secondary;
  border-radius: $radius-md;
  padding: $spacing-3xl;
  width: 100%;
  max-width: 500px;
  box-shadow: $shadow-default;

  h1 {
    color: $color-brand-primary;
    font-size: $font-size-xl;
    font-weight: $font-weight-semibold;
    text-align: center;
    margin-bottom: $spacing-2xl;
  }
}

.signup-form {
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

.signup-button {
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

.success-message {
  background: $color-success-bg;
  border: 1px solid $color-success-border;
  color: $color-success-text;
  padding: $spacing-sm $spacing-md;
  border-radius: $radius-sm;
  font-size: $font-size-sm;
  text-align: center;
}

.login-link {
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