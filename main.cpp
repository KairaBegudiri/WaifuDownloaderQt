#include <QApplication>
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QCheckBox>
#include <QComboBox>
#include <QProgressBar>
#include <QFileDialog>
#include <QMessageBox>
#include <QFrame>
#include <QPixmap>
#include <QThread>
#include <QStyle>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include <stdexcept>

using json = nlohmann::json;

static size_t write_cb(char *ptr, size_t size, size_t nmemb, void *userdata) {
    auto *buf = static_cast<std::vector<char>*>(userdata);
    buf->insert(buf->end(), ptr, ptr + size * nmemb);
    return size * nmemb;
}

static std::vector<char> http_get(const std::string &url) {
    std::vector<char> buf;
    CURL *c = curl_easy_init();
    if (!c) throw std::runtime_error("curl init failed");
    curl_easy_setopt(c, CURLOPT_URL, url.c_str());
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(c, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(c, CURLOPT_USERAGENT, "NekoViewer/4");
    curl_easy_setopt(c, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(c, CURLOPT_FOLLOWLOCATION, 1L);
    CURLcode res = curl_easy_perform(c);
    curl_easy_cleanup(c);
    if (res != CURLE_OK) throw std::runtime_error(curl_easy_strerror(res));
    return buf;
}

struct Source {
    const char *name;
    const char *api_url;      
    const char *nsfw_param;  
    const char *base_url;     
    const char *key1;
    int         idx;
    const char *key2;
};

static const Source SOURCES[] = {
    { "Nekos.moe",
      "https://nekos.moe/api/v1/random/image",
      "param", "https://nekos.moe/image/",
      "images", 0, "id" },
    { "Waifu.im",
      "https://api.waifu.im/search?is_nsfw=",
      "inline", "",
      "images", 0, "url" },
};
static const int N_SOURCES = sizeof(SOURCES) / sizeof(SOURCES[0]);

class Worker : public QThread {
    Q_OBJECT
public:
    Worker(const Source &src, bool nsfw, QObject *parent = nullptr)
        : QThread(parent), m_src(src), m_nsfw(nsfw) {}

signals:
    void done(QByteArray data);
    void error(QString msg);

protected:
    void run() override {
        try {
            std::string nsfw_str = m_nsfw ? "true" : "false";
            std::string api_url  = m_src.api_url;

            if (std::string(m_src.nsfw_param) == "param")
                api_url += std::string("?nsfw=") + nsfw_str;
            else
                api_url += nsfw_str;

            auto raw = http_get(api_url);
            auto j   = json::parse(raw.begin(), raw.end());

            std::string img_url = j[m_src.key1][m_src.idx][m_src.key2];
            if (!m_src.base_url[0] == '\0')
                img_url = std::string(m_src.base_url) + img_url;

            if (img_url.substr(0, 4) != "http")
                throw std::runtime_error("Invalid image URL");

            auto img = http_get(img_url);
            emit done(QByteArray(img.data(), img.size()));
        } catch (const std::exception &e) {
            emit error(QString::fromStdString(e.what()));
        }
    }

private:
    Source m_src;
    bool   m_nsfw;
};

class App : public QWidget {
    Q_OBJECT
public:
    App(QWidget *parent = nullptr) : QWidget(parent), m_worker(nullptr) {
        setWindowTitle("WaifuDownloader");
        setMinimumSize(450, 550);
        resize(700, 800);

        auto *lo = new QVBoxLayout(this);
        lo->setContentsMargins(15, 15, 15, 15);
        lo->setSpacing(10);

        auto *row1 = new QHBoxLayout;
        m_src = new QComboBox;
        for (int i = 0; i < N_SOURCES; ++i)
            m_src->addItem(SOURCES[i].name);
        row1->addWidget(new QLabel("Source:"));
        row1->addWidget(m_src, 1);
        lo->addLayout(row1);

        auto *frame = new QFrame;
        frame->setFrameShape(QFrame::StyledPanel);
        frame->setMinimumHeight(450);
        auto *flo = new QVBoxLayout(frame);
        flo->setContentsMargins(0, 0, 0, 0);
        m_img = new QLabel("Click Refresh to load.");
        m_img->setAlignment(Qt::AlignCenter);
        flo->addWidget(m_img);
        lo->addWidget(frame, 1);

        auto *row2 = new QHBoxLayout;
        m_status = new QLabel("Ready.");
        m_pbar = new QProgressBar;
        m_pbar->setTextVisible(false);
        m_pbar->setMaximumWidth(150);
        m_pbar->setValue(100);
        row2->addWidget(m_status, 1);
        row2->addWidget(m_pbar);
        lo->addLayout(row2);

        auto *row3 = new QHBoxLayout;
        m_nsfw = new QCheckBox("Allow NSFW");
        m_ref = new QPushButton(style()->standardIcon(QStyle::SP_BrowserReload),    "Refresh");
        m_sav = new QPushButton(style()->standardIcon(QStyle::SP_DialogSaveButton), "Save");
        m_sav->setEnabled(false);
        row3->addWidget(m_nsfw);
        row3->addStretch();
        row3->addWidget(m_ref);
        row3->addWidget(m_sav);
        lo->addLayout(row3);

        connect(m_ref, &QPushButton::clicked, this, &App::load);
        connect(m_sav, &QPushButton::clicked, this, &App::save);
        connect(m_src, qOverload<int>(&QComboBox::currentIndexChanged), this, &App::reset);
    }

    ~App() { stopWorker(); }

private slots:
    void reset() {
        m_img->setText(QString("Click Refresh to load.\nSource: %1").arg(m_src->currentText()));
        m_px = QPixmap();
        m_sav->setEnabled(false);
    }

    void load() {
        stopWorker();
        m_ref->setEnabled(false);
        m_sav->setEnabled(false);
        m_src->setEnabled(false);
        m_status->setText("Loading...");
        m_img->setText("Loading...");
        m_pbar->setRange(0, 0);

        m_worker = new Worker(SOURCES[m_src->currentIndex()], m_nsfw->isChecked(), this);
        connect(m_worker, &Worker::done,  this, &App::onDone);
        connect(m_worker, &Worker::error, this, &App::onError);
        connect(m_worker, &Worker::finished, m_worker, &QObject::deleteLater);
        m_worker->start();
    }

    void onDone(QByteArray data) {
        resetUi("Loaded.");
        QPixmap px;
        px.loadFromData(data);
        if (px.isNull()) { onError("Corrupt image data."); return; }
        m_px = px;
        scale();
        m_sav->setEnabled(true);
    }

    void onError(QString msg) {
        resetUi("Error: " + msg);
        m_img->setText("Failed.");
        QMessageBox::critical(this, "Error", msg);
    }

    void save() {
        if (m_px.isNull()) return;
        QString path = QFileDialog::getSaveFileName(this, "Save", "neko.png",
                           "PNG (*.png);;JPEG (*.jpg);;All (*)");
        if (path.isEmpty()) return;
        if (m_px.save(path))
            QMessageBox::information(this, "Done", QString("Saved to '%1'.").arg(path));
        else
            QMessageBox::warning(this, "Error", "Could not save.");
    }

private:
    void stopWorker() {
        if (!m_worker) return;
        if (m_worker->isRunning()) { m_worker->terminate(); m_worker->wait(); }
        m_worker = nullptr;
    }

    void resetUi(const QString &msg) {
        m_ref->setEnabled(true);
        m_src->setEnabled(true);
        m_pbar->setRange(0, 100);
        m_pbar->setValue(100);
        m_status->setText(msg);
        m_worker = nullptr;
    }

    void scale() {
        if (!m_px.isNull())
            m_img->setPixmap(m_px.scaled(m_img->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation));
    }

    void resizeEvent(QResizeEvent *e) override { QWidget::resizeEvent(e); scale(); }

    QComboBox   *m_src;
    QLabel      *m_img, *m_status;
    QProgressBar*m_pbar;
    QCheckBox   *m_nsfw;
    QPushButton *m_ref, *m_sav;
    QPixmap      m_px;
    Worker      *m_worker;
};

int main(int argc, char *argv[]) {
    QApplication::setHighDpiScaleFactorRoundingPolicy(Qt::HighDpiScaleFactorRoundingPolicy::PassThrough);
    QApplication app(argc, argv);
    App w;
    w.show();
    return app.exec();
}

#include "main.moc"
