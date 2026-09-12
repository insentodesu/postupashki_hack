import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-copy">
        <span className="bootstrap__eyebrow">Поступашки / Measurement</span>
        <h1>Смотрите на доказательства, а не на догадки.</h1>
        <p>Campaign, Telegram touch, оплата и ROMI в одной измеримой цепочке.</p>
        <div className="login-chain" aria-label="Цепочка измерения">
          <span>placement</span><i aria-hidden="true" /><span>touch</span><i aria-hidden="true" />
          <span>lead</span><i aria-hidden="true" /><span>revenue</span>
        </div>
      </section>
      <section className="login-card" aria-labelledby="login-title">
        <h2 id="login-title">Вход в рабочую панель</h2>
        <p>Используйте пароль из защищённого окружения проекта.</p>
        <LoginForm />
      </section>
    </main>
  );
}
