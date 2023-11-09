import React, { FC, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Loader from "components/Loader";
import ClientList from "pages/clients/ClientList";
import NoMatch from "components/NoMatch";
import ClientCreate from "pages/clients/ClientCreate";
import ClientDetail from "pages/clients/ClientDetail";
import ClientEdit from "pages/clients/ClientEdit";

const App: FC = () => {
  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/client/list" replace={true} />}
        />
        <Route
          path="/client"
          element={<Navigate to="/client/list" replace={true} />}
        />
        <Route path="/client/create" element={<ClientCreate />} />
        <Route path="/client/detail/:client" element={<ClientDetail />} />
        <Route path="/client/edit/:client" element={<ClientEdit />} />
        <Route path="/client/list" element={<ClientList />} />
        <Route path="*" element={<NoMatch />} />
      </Routes>
    </Suspense>
  );
};

export default App;
