-- Cliente prioritario: marca no contato. Efeitos: urgencia minima "alta", vai na frente no
-- quadro e os alertas de demanda parada chegam mais cedo.
ALTER TABLE contacts ADD COLUMN priority boolean NOT NULL DEFAULT false;
