# AvaliarModeloML.py — avaliação offline do modelo com chamados fechados do GLPI

import os

from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

from DbMigracao import ClDbMigracao
from ML import ClML


def main():
    meses = int(os.getenv("ML_FEEDBACK_MESES", "6"))
    if not ClDbMigracao().aplicar_migracao_ambiente():
        print("AVISO: migração Fase 2 incompleta.")
    clml = ClML()

    print("=" * 60)
    print("AVALIAÇÃO OFFLINE DO MODELO ML (chamados fechados GLPI)")
    print("=" * 60)

    dt = clml.pesquisar_dados_treinamento_ml()
    if dt is None or dt.empty:
        print("Nenhum dado de feedback disponível. Execute SincronizarFeedbackGLPI.py primeiro.")
        return

    texts, labels, _weights = clml._preparar_dataset(dt)
    print(f"\nRegistros válidos para avaliação: {len(texts)}")
    print(f"Classes distintas: {len(set(labels))} -> {sorted(set(labels))}")

    if len(texts) < 30 or len(set(labels)) < 2:
        print("Volume insuficiente para hold-out estratificado.")
        return

    indices = list(range(len(texts)))
    train_idx, test_idx = train_test_split(
        indices, test_size=0.2, random_state=42, stratify=labels
    )
    train_texts = [texts[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]

    pacote = clml._fit_modelo(train_texts, train_labels)
    classifier, vectorizer, label_encoder, _ = pacote

    X_test = vectorizer.transform(test_texts)
    y_pred = label_encoder.inverse_transform(classifier.predict(X_test))
    y_true = test_labels

    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"\nF1-macro (hold-out 20%): {f1:.3f}")
    print("\nRelatório por equipe:")
    print(classification_report(y_true, y_pred, zero_division=0))

    print("Matriz de confusão (linhas=real, colunas=predito):")
    labels_ord = sorted(set(y_true) | set(y_pred))
    mat = confusion_matrix(y_true, y_pred, labels=labels_ord)
    header = "     " + " ".join(f"{l:>5}" for l in labels_ord)
    print(header)
    for i, row_label in enumerate(labels_ord):
        print(f"{row_label:>5} " + " ".join(f"{v:>5}" for v in mat[i]))

    modelo = clml.le_modelo_ml()
    if modelo[0] is not None and modelo[3].get("f1_macro") is not None:
        print(f"\nF1-macro do modelo implantado (ModeloML.pkl): {modelo[3]['f1_macro']:.3f}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
