cmake_minimum_required(VERSION 3.16)
project(WaifuDownloader LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(CURL REQUIRED)

find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
    include(FetchContent)
    FetchContent_Declare(json
        URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz)
    FetchContent_MakeAvailable(json)
endif()

add_executable(waifudownloader main.cpp)

target_link_libraries(waifudownloader
    Qt6::Widgets
    CURL::libcurl
    nlohmann_json::nlohmann_json
)

include(GNUInstallDirs)

install(TARGETS waifudownloader
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

install(FILES src/WaifuDownloaderQt.desktop
    DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)

install(FILES src/moe.nyarchlinux.waifudownloader256.png
    DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/256x256/apps
    RENAME moe.nyarchlinux.waifudownloader.png)
