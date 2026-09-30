import { RoleSwitcher } from "../components/RoleSwitcher";

export function SignInPage() {
  return (
    <div className="signin">
      <div className="panel">
        <div className="eyebrow">Development sign-in</div>
        <h2 style={{ margin: 0, fontFamily: "var(--display)", fontStretch: "86%" }}>MRM Governance MIS</h2>
        <p className="note">
          Choose a user and one of their roles. What you can do is decided by the server for that role.
          Production uses the enterprise identity provider instead.
        </p>
        <label className="field">
          Act as
          <RoleSwitcher />
        </label>
      </div>
    </div>
  );
}
