import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell, RequireAuth, RequireRole } from "./components/AppShell";
import { BoardPage } from "./features/board/BoardPage";
import { AgendaPage } from "./features/agenda/AgendaPage";
import { ContactsPage } from "./features/contacts/ContactsPage";
import { Login } from "./features/login/Login";
import { PanelPage } from "./features/panel/PanelPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<BoardPage />} />
          <Route path="agenda" element={<AgendaPage />} />
          <Route
            path="painel"
            element={
              <RequireRole roles={["socio"]}>
                <PanelPage />
              </RequireRole>
            }
          />
          <Route
            path="contatos"
            element={
              <RequireRole roles={["socio", "gestor"]}>
                <ContactsPage />
              </RequireRole>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
