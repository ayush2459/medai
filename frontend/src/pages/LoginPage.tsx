import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState("admin@medintel.ai");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to sign in. Check your credentials and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f7f9] lg:grid lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[#123c4b] p-12 text-white lg:flex lg:flex-col lg:justify-between xl:p-16">
        <div className="pointer-events-none absolute -right-32 top-24 h-[28rem] w-[28rem] rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -right-16 top-40 h-[22rem] w-[22rem] rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -bottom-40 -left-24 h-[28rem] w-[28rem] rounded-full bg-[#087f8c]/20 blur-3xl" />

        <div className="relative flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#62d4ba] text-xl font-black text-[#123c4b]">M</div>
          <div>
            <p className="text-lg font-bold tracking-tight">MedIntel AI</p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#b9d8df]">Hospital intelligence</p>
          </div>
        </div>

        <div className="relative my-14 max-w-xl">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-2 text-[10px] font-bold tracking-[0.17em] text-[#b9e9e4]">
            <span className="h-2 w-2 rounded-full bg-[#62d4ba]" />
            INTELLIGENCE THAT CARES
          </div>
          <h1 className="text-4xl font-bold leading-[1.15] tracking-tight xl:text-6xl">
            See the whole picture.
            <span className="mt-2 block text-[#75d8ca]">Make care clearer.</span>
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-[#c5dbe1]">
            A clearer view of hospital operations, patient records and
            model-assisted insights — designed to help care teams stay informed.
          </p>

          <div className="mt-10 grid grid-cols-3 gap-3">
            {[
              { value: "01", label: "Connected workspace" },
              { value: "24/7", label: "Clinical visibility" },
              { value: "AI+", label: "Decision support" },
            ].map((item) => (
              <div key={item.value} className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                <p className="text-2xl font-bold">{item.value}</p>
                <p className="mt-2 text-xs leading-5 text-[#b9d0d8]">{item.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative flex items-center justify-between gap-4 border-t border-white/15 pt-5 text-xs text-[#b9d0d8]">
          <span>Built for better-informed care teams</span>
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#62d4ba]" />Secure workspace</span>
        </div>
      </section>

      <section className="flex min-h-screen flex-col justify-between px-5 py-6 sm:px-10 sm:py-9 lg:px-12 xl:px-20">
        <div className="flex items-center gap-3 lg:hidden">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#087f8c] font-black text-white">M</div>
          <div>
            <p className="font-bold text-[#193342]">MedIntel AI</p>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#8797a1]">Hospital intelligence</p>
          </div>
        </div>

        <div className="mx-auto w-full max-w-md py-12">
          <div className="mb-8 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#d8eded] bg-[#e5f6f4] text-2xl text-[#087f8c]">↗</div>
          <p className="text-xs font-bold uppercase tracking-[0.17em] text-[#087f8c]">Welcome back</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-[#193342] sm:text-4xl">Sign in to your workspace</h2>
          <p className="mt-3 text-sm leading-6 text-[#738391]">Enter your account details to access your hospital intelligence dashboard.</p>

          <form onSubmit={handleSubmit} className="mt-9 space-y-5">
            <div>
              <label htmlFor="email" className="mb-2 block text-sm font-semibold text-[#294452]">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@hospital.org"
                className="w-full rounded-xl border border-[#dfe7ec] bg-white px-4 py-3.5 text-sm text-[#193342] outline-none transition placeholder:text-[#a0adb5] focus:border-[#087f8c] focus:ring-4 focus:ring-[#087f8c]/10"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-semibold text-[#294452]">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-[#dfe7ec] bg-white px-4 py-3.5 pr-20 text-sm text-[#193342] outline-none transition placeholder:text-[#a0adb5] focus:border-[#087f8c] focus:ring-4 focus:ring-[#087f8c]/10"
                />
                <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-semibold text-[#087f8c] hover:bg-[#edf7f7]">
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <div role="alert" className="rounded-xl border border-[#f0cdcf] bg-[#fff5f5] p-4 text-sm leading-5 text-[#b8474c]">
                <p className="font-semibold">Sign-in unsuccessful</p>
                <p className="mt-1">{error}</p>
              </div>
            )}

            <button type="submit" disabled={isSubmitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#087f8c] px-5 py-3.5 text-sm font-bold text-white shadow-lg shadow-[#087f8c]/15 transition hover:bg-[#06616b] focus:outline-none focus:ring-4 focus:ring-[#087f8c]/20 disabled:cursor-not-allowed disabled:opacity-60">
              {isSubmitting ? "Signing in…" : <>Sign in to MedIntel <span aria-hidden="true">→</span></>}
            </button>
          </form>

          <div className="mt-6 flex items-start gap-3 rounded-xl border border-[#e3eaf0] bg-white p-4">
            <span className="mt-0.5 text-[#087f8c]">◇</span>
            <div>
              <p className="text-xs font-semibold text-[#526b78]">Protected workspace</p>
              <p className="mt-1 text-xs leading-5 text-[#8797a1]">Access depends on your assigned account and role. Use your authorized credentials to continue.</p>
            </div>
          </div>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-[#e3eaf0] pt-5 text-xs text-[#8797a1]">
          <span>MedIntel AI · Hospital intelligence</span>
          <span>For authorized users only</span>
        </footer>
      </section>
    </main>
  );
}
