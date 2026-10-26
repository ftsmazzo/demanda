import { Navigate, Route, Routes } from "react-router-dom";
import { SectorsPage } from "./features/sectors/SectorsPage";
import { AppShell, RequireAuth, RequireRole } from "./components/AppShell";
import { BoardPage } from "./features/board/BoardPage";
import { AgendaPage } from "./features/agenda/AgendaPage";
import { ConversationPage } from "./features/conversation/ConversationPage";
import { ConversationsPage } from "./features/conversations/ConversationsPage";
import { TodayPage } from "./features/today/TodayPage";
import { ContactsPage } from "./features/contacts/ContactsPage";
import { Login } from "./features/login/Login";
import { PanelPage } from "./features/panel/PanelPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<TodayPage />} />
          <Route path="quadro" element={<BoardPage />} />
          <Route
            path="conversas"
            element={
              <RequireRole roles={["socio", "gestor"]}>
                <ConversationsPage />
              </RequireRole>
            }
          />
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
            path="setores"
            element={
              <RequireRole roles={["socio"]}>
                <SectorsPage />
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
          <Route
            path="contatos/:contactId/conversa"
            element={
              <RequireRole roles={["socio", "gestor"]}>
                <ConversationPage />
              </RequireRole>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
