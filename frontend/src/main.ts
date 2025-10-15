// Import styles and assets
import './style.css';
import javascriptLogo from './javascript.svg';
import viteLogo from '/vite.svg';

// Import functions and scripts
import { setupCounter } from './counter';
import './js/payments';

// Safely select the app container
const app = document.querySelector<HTMLDivElement>('#app');

if (app) {
  app.innerHTML = `
    <div>
      <a href="https://vite.dev" target="_blank">
        <img src="${viteLogo}" class="logo" alt="Vite logo" />
      </a>
      <a href="https://developer.mozilla.org/en-US/docs/Web/JavaScript" target="_blank">
        <img src="${javascriptLogo}" class="logo vanilla" alt="JavaScript logo" />
      </a>
      <h1>Hello Vite + TypeScript!</h1>
      <div class="card">
        <button id="counter" type="button"></button>
      </div>
      <p class="read-the-docs">
        Click on the Vite logo to learn more
      </p>
    </div>
  `;

  // Initialize the counter
  const counterButton = document.querySelector<HTMLButtonElement>('#counter');
  if (counterButton) {
    setupCounter(counterButton);
  }
} else {
  console.error('❌ Element with id="app" not found.');
}
